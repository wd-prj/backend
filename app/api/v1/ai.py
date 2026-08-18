from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_employee
from app.models.employee import Employee
from app.schemas.ai import AIChatRequest, AIChatResponse, GroundedToolCall, GroundedBreakdown
from app.ai.agent import run_leave_agent

router = APIRouter(prefix="/ai", tags=["AI Assistant"])


@router.post("/chat", response_model=AIChatResponse)
def chat_with_leave_agent(
    req: AIChatRequest,
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """
    Interacts with the single primary LeaveAgent LangGraph workflow.
    Tool calls are safely executed against authenticated domain services.
    """
    history_dicts = [{"role": h.role, "content": h.content} for h in (req.history or [])]

    result = run_leave_agent(
        db=db,
        employee_id=current_employee.id,
        user_message=req.message,
        chat_history=history_dicts,
    )

    breakdown_dto = None
    if result.get("breakdown"):
        bd = result["breakdown"]
        breakdown_dto = GroundedBreakdown(
            calendar_days=bd.get("calendar_days"),
            weekend_days=bd.get("weekend_days"),
            holiday_days=bd.get("holiday_days"),
            working_days=bd.get("working_days"),
            balance_before=bd.get("balance_before"),
            balance_after=bd.get("balance_after"),
            approval_route=bd.get("approval_route"),
        )

    tool_dtos = [
        GroundedToolCall(
            tool_name=t["tool_name"],
            tool_input=t["tool_input"],
            tool_output=t["tool_output"],
        )
        for t in result.get("tool_calls_executed", [])
    ]

    return AIChatResponse(
        reply=result["reply"],
        recommendation=result.get("recommendation"),
        reason=result.get("reason"),
        breakdown=breakdown_dto,
        tool_calls_executed=tool_dtos,
        is_grounded=result.get("is_grounded", True),
    )
