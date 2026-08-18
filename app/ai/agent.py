import json
import logging
from typing import Annotated, List, Dict, Any, Optional, TypedDict
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from sqlalchemy.orm import Session
from app.ai.provider import get_ai_model, MockLeaveChatModel
from app.ai.tools import build_tool_registry
from app.ai.prompts import build_system_prompt
from app.services.employee_service import EmployeeService

logger = logging.getLogger(__name__)


class LeaveAgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    employee_id: str
    user_role: str
    location_id: str
    department_id: str
    tool_history: List[Dict[str, Any]]


def run_leave_agent(
    db: Session,
    employee_id: str,
    user_message: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Executes the single primary LeaveAgent LangGraph workflow.
    Orchestrates grounded tool execution and returns explainable responses.
    Includes automated fallback to deterministic engine on remote rate limits.
    """
    employee_service = EmployeeService(db)
    emp = employee_service.get_employee_by_id(employee_id)

    emp_name = emp.full_name if emp else "Employee"
    emp_desig = emp.designation if emp else "Staff"
    dept_name = emp.department.name if emp and emp.department else "General"
    loc_name = emp.location.name if emp and emp.location else "HQ"

    # 1. Build bound tools
    tools = build_tool_registry(db, employee_id)
    tool_map = {t.name: t for t in tools}

    # 2. Get AI Model
    model = get_ai_model()
    try:
        model_with_tools = model.bind_tools(tools)
    except Exception:
        model = MockLeaveChatModel()
        model_with_tools = model.bind_tools(tools)

    # 3. Setup Initial State with dynamically enriched caller context
    sys_prompt = build_system_prompt(
        employee_name=emp_name,
        designation=emp_desig,
        department_name=dept_name,
        location_name=loc_name,
        employee_id=employee_id,
        current_date="2026-08-18",
    )
    initial_messages: List[BaseMessage] = [SystemMessage(content=sys_prompt)]
    
    if chat_history:
        for item in chat_history[-6:]:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role == "user":
                initial_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                initial_messages.append(AIMessage(content=content))

    initial_messages.append(HumanMessage(content=user_message))

    tool_history_tracker: List[Dict[str, Any]] = []

    # 4. Graph Nodes
    def agent_node(state: LeaveAgentState) -> Dict[str, Any]:
        nonlocal model_with_tools
        try:
            response = model_with_tools.invoke(state["messages"])
        except Exception as exc:
            logger.warning(f"Live LLM provider error: {exc}. Falling back to deterministic tool execution.")
            fallback_model = MockLeaveChatModel().bind_tools(tools)
            response = fallback_model.invoke(state["messages"])
        return {"messages": [response]}

    def tool_node(state: LeaveAgentState) -> Dict[str, Any]:
        last_message = state["messages"][-1]
        tool_messages: List[ToolMessage] = []

        if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                name = tool_call["name"]
                args = tool_call["args"]
                call_id = tool_call.get("id", f"call_{name}")

                tool_func = tool_map.get(name)
                if tool_func:
                    try:
                        raw_result = tool_func.invoke(args)
                    except Exception as e:
                        raw_result = json.dumps({"error": str(e)})
                else:
                    raw_result = json.dumps({"error": f"Tool '{name}' not found"})

                try:
                    parsed_out = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
                except Exception:
                    parsed_out = raw_result

                tool_history_tracker.append({
                    "tool_name": name,
                    "tool_input": args,
                    "tool_output": parsed_out,
                })

                tool_messages.append(
                    ToolMessage(
                        content=raw_result if isinstance(raw_result, str) else json.dumps(raw_result),
                        name=name,
                        tool_call_id=call_id,
                    )
                )

        return {
            "messages": tool_messages,
            "tool_history": tool_history_tracker,
        }

    def should_continue(state: LeaveAgentState) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    # 5. Build Graph
    workflow = StateGraph(LeaveAgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")

    app = workflow.compile()

    # 6. Execute Graph
    try:
        final_state = app.invoke({
            "messages": initial_messages,
            "employee_id": employee_id,
            "user_role": "EMPLOYEE",
            "location_id": emp.location_id if emp else "",
            "department_id": emp.department_id if emp else "",
            "tool_history": [],
        })
    except Exception as e:
        logger.error(f"Graph execution error: {e}")
        # Fallback to mock synthesis
        fallback_model = MockLeaveChatModel().bind_tools(tools)
        fallback_msg = fallback_model.invoke(initial_messages)
        final_state = {"messages": [fallback_msg]}

    # Extract final AIMessage
    final_messages = final_state["messages"]
    last_ai_msg = ""
    for msg in reversed(final_messages):
        if isinstance(msg, AIMessage) and msg.content:
            last_ai_msg = str(msg.content)
            break

    # Extract structured breakdown if available in tool calls
    breakdown_data = None
    recommendation = None
    reason = None

    for th in tool_history_tracker:
        out = th.get("tool_output", {})
        if isinstance(out, dict) and "working_days" in out:
            breakdown_data = {
                "calendar_days": out.get("calendar_days"),
                "weekend_days": out.get("weekend_days"),
                "holiday_days": out.get("holiday_days"),
                "working_days": out.get("working_days"),
                "balance_before": out.get("available_balance_before"),
                "balance_after": out.get("available_balance_after"),
                "approval_route": out.get("approval_route"),
            }
            if out.get("is_valid") is True:
                recommendation = "Eligible to Request"
                reason = "Request meets all location policy guidelines and balance quota."
            elif out.get("is_valid") is False:
                recommendation = "Policy Restriction"
                reason = "; ".join(out.get("policy_violations", []))

    return {
        "reply": last_ai_msg or "I have processed your leave inquiry.",
        "recommendation": recommendation,
        "reason": reason,
        "breakdown": breakdown_data,
        "tool_calls_executed": tool_history_tracker,
        "is_grounded": len(tool_history_tracker) > 0,
    }
