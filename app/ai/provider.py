import json
import logging
import re
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
    Deterministic Domain AI Assistant for Workforce & PTO Orchestration.
    Understands HR leave queries, invokes required domain tools, and constructs
    grounded, explainable responses tailored to user intent.
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
        # Check the user message history
        user_text = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                user_text = str(m.content).lower()
                break

        # Check if we are in the synthesis phase with ToolMessages
        tool_messages = [m for m in messages if isinstance(m, ToolMessage)]

        if tool_messages:
            tool_data = {}
            for tm in tool_messages:
                try:
                    tool_data[tm.name] = json.loads(tm.content) if isinstance(tm.content, str) else tm.content
                except Exception:
                    tool_data[tm.name] = tm.content

            synthesis_parts = []
            
            val = tool_data.get("validate_leave_request")
            wf = tool_data.get("get_approval_workflow")
            holidays = tool_data.get("get_holidays")
            policies = tool_data.get("get_leave_policies")
            bal = tool_data.get("get_leave_balance")
            calc = tool_data.get("calculate_leave_days")

            # 1. Approval Workflow Intent
            if wf or any(w in user_text for w in ["approve", "approval", "approver", "who needs", "tiers", "sign off"]):
                steps = wf if isinstance(wf, list) else []
                # Extract days mentioned if available
                days_match = re.search(r"(\d+)\s*(?:working\s*)?days?", user_text)
                days_num = int(days_match.group(1)) if days_match else 5

                synthesis_parts.append(
                    f"### Authoritative Approval Hierarchy for {days_num} Working Days\n"
                    f"Under ZenithHR's deterministic governance policies, a **{days_num}-day absence** requires the following multi-tier approval routing:"
                )

                if steps:
                    for s in steps:
                        role_title = s.get("role", "MANAGER").replace("_", " ").title()
                        approver = s.get("approver", "Assigned Lead")
                        order = s.get("step_order", 1)
                        synthesis_parts.append(f"* **Step {order} ({role_title})**: Approved by **{approver}**")
                else:
                    if days_num <= 2:
                        synthesis_parts.append("* **Step 1 (Direct Manager)**: Requires standard sign-off from your direct team manager.")
                    elif days_num <= 5:
                        synthesis_parts.append("* **Step 1 (Direct Manager)**: Primary review and team coverage assessment from your direct manager.")
                        synthesis_parts.append("* **Step 2 (Department Head)**: Executive departmental approval from your VP / Department Head.")
                    else:
                        synthesis_parts.append("* **Step 1 (Direct Manager)**: Primary review from your direct manager.")
                        synthesis_parts.append("* **Step 2 (Department Head)**: Departmental authorization from your VP / Department Head.")
                        synthesis_parts.append("* **Step 3 (HR Admin Lead)**: Executive compliance approval from HR Leadership.")

                synthesis_parts.append(
                    "\n> **Policy Rule Thresholds**:\n"
                    "> • **1–2 days**: Single-tier Direct Manager approval.\n"
                    "> • **3–5 days**: Two-tier (Direct Manager → Department Head).\n"
                    "> • **>5 days**: Three-tier (Direct Manager → Department Head → HR Admin)."
                )

            # 2. Leave Suggestions / Recommendations
            elif any(w in user_text for w in ["suggest", "recommend", "best time", "plan", "bridge", "long weekend"]):
                synthesis_parts.append("### 🗓️ Strategic Leave & Long Weekend Recommendations")
                synthesis_parts.append(
                    "Maximize your time off by pairing upcoming recognized holidays with minimal PTO working days:"
                )

                h_list = holidays if isinstance(holidays, list) else []
                if h_list:
                    for h in h_list[:3]:
                        synthesis_parts.append(
                            f"* 🌟 **{h.get('name')} ({h.get('date')})**:\n"
                            f"  - Combine with 1–2 days of Annual Leave (PTO) to unlock a **4-day or 5-day continuous rest period** while consuming minimal quota."
                        )
                else:
                    synthesis_parts.append(
                        "* **Upcoming Bridge Window**: Take a Friday or Monday adjacent to a weekend for a 3-day recharge.\n"
                        "* **Quarterly PTO Distribution**: Distribute 3–4 days every quarter to prevent balance burnout."
                    )

                if bal:
                    balances = bal if isinstance(bal, list) else []
                    annual = next((b for b in balances if "Annual" in b.get("leave_type_name", "")), None)
                    if annual:
                        synthesis_parts.append(
                            f"\n* **Available Quota**: You currently have **{fmt_days(annual.get('available_balance'))} Annual PTO days** available to plan."
                        )

            # 3. Pre-Validation / Specific Dates
            elif val:
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

            # 4. Calculation Only
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

            # 5. Policies
            elif policies:
                pol_list = policies if isinstance(policies, list) else []
                synthesis_parts.append("### Authorized Location Leave Policies")
                for p in pol_list:
                    synthesis_parts.append(
                        f"* **{p.get('leave_type', 'Policy')}**:\n"
                        f"  - Max Consecutive Days: {p.get('max_consecutive_days', 10)} days\n"
                        f"  - Advance Notice Required: {p.get('advance_notice_days', 0)} days\n"
                        f"  - Carry-Forward Cap: {fmt_days(p.get('carry_forward_limit', 5))} days"
                    )

            # 6. Holidays
            elif holidays:
                h_list = holidays if isinstance(holidays, list) else []
                h_lines = [f"* **{h.get('date')}**: {h.get('name')}" for h in h_list]
                synthesis_parts.append(
                    f"### Verified Location Holidays\n" + ("\n".join(h_lines) if h_lines else "No upcoming holidays found.")
                )

            # 7. Balances
            elif bal:
                balances = bal if isinstance(bal, list) else []
                bal_lines = [
                    f"* **{b.get('leave_type_name')}**: {fmt_days(b.get('available_balance'))} days available ({fmt_days(b.get('pending_reserved'))} pending, {fmt_days(b.get('approved_used'))} used)"
                    for b in balances
                ]
                synthesis_parts.append(
                    f"### Current Verified Leave Balances\n" + "\n".join(bal_lines)
                )

            else:
                synthesis_parts.append("Based on the verified HR records retrieved above, your request has been analyzed and confirmed.")

            ai_content = "\n\n".join(synthesis_parts)
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=ai_content))])

        # Step 1: Tool Intent Classification
        tool_calls = []

        # 1. Approval questions
        if any(w in user_text for w in ["approve", "approval", "approver", "who needs", "tiers", "who approves"]):
            days_match = re.search(r"(\d+)\s*(?:working\s*)?days?", user_text)
            days_num = float(days_match.group(1)) if days_match else 5.0
            tool_calls.append({
                "name": "get_approval_workflow",
                "args": {"working_days": days_num},
                "id": "call_wf_1",
                "type": "tool_call",
            })

        # 2. Suggestions / Recommendations
        elif any(w in user_text for w in ["suggest", "recommend", "best time", "plan", "bridge", "long weekend"]):
            tool_calls.append({
                "name": "get_holidays",
                "args": {"year": 2026},
                "id": "call_hol_1",
                "type": "tool_call",
            })
            tool_calls.append({
                "name": "get_leave_balance",
                "args": {},
                "id": "call_bal_1",
                "type": "tool_call",
            })

        # 3. Holidays
        elif any(w in user_text for w in ["holiday", "calendar", "festival", "days off"]):
            tool_calls.append({
                "name": "get_holidays",
                "args": {"year": 2026},
                "id": "call_hol_1",
                "type": "tool_call",
            })

        # 4. Dates / Leave Validation
        elif any(w in user_text for w in ["august", "aug", "september", "take leave", "request leave", "next friday", "can i take", "apply for"]):
            start_d = "2026-08-24" if "aug" in user_text else "2026-08-21"
            end_d = "2026-08-28" if "aug" in user_text else "2026-08-21"
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

        # 5. Policies
        elif any(w in user_text for w in ["policy", "policies", "rules", "limit", "notice", "consecutive", "carry"]):
            tool_calls.append({
                "name": "get_leave_policies",
                "args": {},
                "id": "call_pol_1",
                "type": "tool_call",
            })

        # 6. Balances
        elif any(w in user_text for w in ["balance", "quota", "how much leave", "remaining", "days left"]):
            tool_calls.append({
                "name": "get_leave_balance",
                "args": {},
                "id": "call_bal_1",
                "type": "tool_call",
            })

        else:
            # Contextual default
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
        max_retries=1,
    )
