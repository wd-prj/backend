import json
import logging
from typing import Any, List, Optional, Sequence
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)


def fmt_days(val: Any) -> str:
    """Formats numeric days cleanly (e.g. 3.0 -> '3', 2.5 -> '2.5')."""
    if val is None:
        return "0"
    try:
        f = float(val)
        return str(int(f)) if f.is_integer() else f"{f:.1f}"
    except (ValueError, TypeError):
        return str(val)


class MockLeaveChatModel(BaseChatModel):
    """
    Deterministic Mock LLM Provider for offline evaluation and testing.
    Understands HR leave queries, invokes required LangGraph tools, and constructs
    grounded, explainable responses using real domain data.
    """
    tools: List[Any] = []

    @property
    def _llm_type(self) -> str:
        return "mock_leave_orchestrator"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "MockLeaveChatModel":
        self.tools = list(tools)
        return self

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Check the last message
        last_msg = messages[-1] if messages else None
        
        # If the last message was a ToolMessage, synthesize final grounded explanation
        tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
        
        if tool_messages:
            # We have tool execution results, build grounded synthesis
            tool_data = {}
            for tm in tool_messages:
                try:
                    tool_data[tm.name] = json.loads(tm.content) if isinstance(tm.content, str) else tm.content
                except Exception:
                    tool_data[tm.name] = tm.content

            synthesis_parts = []
            
            # Format breakdown if calculation tool was called
            calc = tool_data.get("calculate_leave_days")
            bal = tool_data.get("get_leave_balance")
            val = tool_data.get("validate_leave_request")
            wf = tool_data.get("get_approval_workflow")
            holidays = tool_data.get("get_holidays")
            policies = tool_data.get("get_leave_policies")

            if val:
                is_valid = val.get("is_valid", True)
                wk_days = fmt_days(val.get("working_days", 0))
                cal_days = fmt_days(val.get("calendar_days", 0))
                wknd_days = fmt_days(val.get("weekend_days", 0))
                hol_days = fmt_days(val.get("holiday_days", 0))
                avail_before = fmt_days(val.get("available_balance_before", 0))
                avail_after = fmt_days(val.get("available_balance_after", 0))
                route = val.get("approval_route", ["Manager"])
                violations = val.get("policy_violations", [])

                if is_valid:
                    synthesis_parts.append(
                        f"### Recommendation\n✅ **You can request this leave.** Your request satisfies all HR policies and available quota.\n"
                    )
                    synthesis_parts.append(
                        f"### Reason & Policy Context\n* **Calendar Window**: {cal_days} calendar days requested.\n"
                        f"* **Non-Working Days**: {wknd_days} weekend days + {hol_days} recognized location holiday(s) deducted.\n"
                        f"* **Net Working Leave Impact**: **{wk_days} working day(s)** will be reserved from your balance.\n"
                        f"* **Balance Change**: Available quota goes from **{avail_before} days** to **{avail_after} days**.\n"
                        f"* **Authoritative Approval Route**: Routed to {' → '.join(route)} based on duration rules."
                    )
                else:
                    synthesis_parts.append(
                        f"### Recommendation\n⚠️ **This leave request cannot be approved as selected.**\n"
                    )
                    synthesis_parts.append(
                        f"### Reason & Violations\n" + "\n".join([f"* ❌ {v}" for v in violations])
                    )
            elif calc:
                wk_days = fmt_days(calc.get("working_days", 0))
                cal_days = fmt_days(calc.get("calendar_days", 0))
                wknd_days = fmt_days(calc.get("weekend_days", 0))
                hol_days = fmt_days(calc.get("holiday_days", 0))
                synthesis_parts.append(
                    f"### Working Day Impact Analysis\n"
                    f"The requested window spans **{cal_days} calendar days** containing:\n"
                    f"* **{wknd_days} weekend days**\n"
                    f"* **{hol_days} location holiday days**\n"
                    f"* **Net {wk_days} working leave days** required."
                )
            elif bal:
                balances = bal if isinstance(bal, list) else []
                bal_lines = [
                    f"* **{b.get('leave_type_name')}**: {fmt_days(b.get('available_balance'))} days available ({fmt_days(b.get('pending_reserved'))} pending, {fmt_days(b.get('approved_used'))} used)"
                    for b in balances
                ]
                synthesis_parts.append(
                    f"### Current Verified Leave Balances\n" + "\n".join(bal_lines)
                )
            elif holidays:
                h_list = holidays if isinstance(holidays, list) else []
                h_lines = [f"* **{h.get('date')}**: {h.get('name')}" for h in h_list]
                synthesis_parts.append(
                    f"### Verified Location Holidays\n" + ("\n".join(h_lines) if h_lines else "No upcoming holidays found.")
                )
            else:
                synthesis_parts.append("Based on the verified HR records retrieved above, your request has been analyzed.")

            ai_content = "\n\n".join(synthesis_parts)
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=ai_content))])

        # If user message, inspect text and emit appropriate tool call(s)
        user_text = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                user_text = str(m.content).lower()
                break

        # Check intent and trigger tool calls
        tool_calls = []

        if any(w in user_text for w in ["balance", "quota", "how much leave", "remaining", "days left"]):
            tool_calls.append({
                "name": "get_leave_balance",
                "args": {},
                "id": "call_bal_1",
                "type": "tool_call",
            })
        elif any(w in user_text for w in ["holiday", "calendar", "festival", "days off"]):
            tool_calls.append({
                "name": "get_holidays",
                "args": {"year": 2026},
                "id": "call_hol_1",
                "type": "tool_call",
            })
        elif any(w in user_text for w in ["august 20", "aug 20", "take leave", "request leave", "next friday", "can i take"]):
            start_d = "2026-08-20" if "aug" in user_text else "2026-08-21"
            end_d = "2026-08-25" if "aug" in user_text else "2026-08-21"
            tool_calls.append({
                "name": "validate_leave_request",
                "args": {
                    "leave_type_code": "ANNUAL",
                    "start_date": start_d,
                    "end_date": end_d,
                },
                "id": "call_val_1",
                "type": "tool_call",
            })
        elif any(w in user_text for w in ["policy", "rules", "limit", "notice", "consecutive"]):
            tool_calls.append({
                "name": "get_leave_policies",
                "args": {},
                "id": "call_pol_1",
                "type": "tool_call",
            })
        else:
            tool_calls.append({
                "name": "get_leave_balance",
                "args": {},
                "id": "call_def_1",
                "type": "tool_call",
            })

        ai_msg = AIMessage(content="", tool_calls=tool_calls)
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])


def get_ai_model() -> BaseChatModel:
    """
    Universal Model Factory supporting LiteLLM routing, OpenAI, OpenRouter, OpenCode Zen,
    Ollama, vLLM, DeepSeek, Anthropic, Gemini, and resilient deterministic Mock fallback.
    """
    provider = settings.LLM_PROVIDER.lower().strip()
    api_key = settings.LLM_API_KEY.strip()
    model_name = settings.LLM_MODEL.strip()

    if provider == "mock" or not api_key:
        return MockLeaveChatModel()

    clean_model = model_name.replace("openai/", "").replace("deepseek/", "")

    return ChatOpenAI(
        model=clean_model,
        api_key=api_key,
        base_url=settings.LLM_BASE_URL if settings.LLM_BASE_URL else None,
        temperature=settings.LLM_TEMPERATURE,
    )
