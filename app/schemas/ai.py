from typing import List, Optional, Any, Dict
from pydantic import BaseModel


class ChatMessageItem(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class AIChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessageItem]] = []


class GroundedToolCall(BaseModel):
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Any


class GroundedBreakdown(BaseModel):
    calendar_days: Optional[int] = None
    weekend_days: Optional[int] = None
    holiday_days: Optional[int] = None
    working_days: Optional[float] = None
    balance_before: Optional[float] = None
    balance_after: Optional[float] = None
    approval_route: Optional[List[str]] = None


class AIChatResponse(BaseModel):
    reply: str
    recommendation: Optional[str] = None
    reason: Optional[str] = None
    breakdown: Optional[GroundedBreakdown] = None
    tool_calls_executed: List[GroundedToolCall] = []
    is_grounded: bool = True
