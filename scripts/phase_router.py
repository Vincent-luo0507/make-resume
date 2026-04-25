"""Decide which Skill phase to run based on workspace state + user intent.

The router takes the deterministic workspace status (from
`state.validate_workspace_state`) and layers user intent on top:

    - `add_template` intent always wins (user explicitly asked).
    - Otherwise the workspace status maps to init/update/generate/recovery.

Old behaviour (v1) used only `initialized_at` + `changes_detected` bool. That
missed the case where state.json existed but the referenced profile was gone
— leaving the Skill to try to parse a file that didn't exist.
"""

from typing import Literal

Phase = Literal["init", "update", "generate", "add_template", "recovery"]

# Chinese: any mention of 模板 (template) signals template-related intent.
# English: exact substrings, case-insensitive.
_ADD_TEMPLATE_CHINESE = ("模板",)
_ADD_TEMPLATE_ENGLISH = ("add template", "change template")


def _is_template_intent(user_intent: str | None) -> bool:
    if not user_intent:
        return False
    intent_lower = user_intent.lower()
    if any(kw in user_intent for kw in _ADD_TEMPLATE_CHINESE):
        return True
    if any(kw in intent_lower for kw in _ADD_TEMPLATE_ENGLISH):
        return True
    return False


def decide_phase(
    workspace_status: str,
    user_intent: str | None = None,
) -> Phase:
    """Return the phase to execute.

    Args:
        workspace_status: one of cold_start|incremental|fast_generate|recovery
            (from `state.validate_workspace_state`).
        user_intent: the user's latest message (free text); keyword-matched
            for template-related intents.
    """
    if _is_template_intent(user_intent):
        return "add_template"

    if workspace_status == "cold_start":
        return "init"
    if workspace_status == "recovery":
        return "recovery"
    if workspace_status == "incremental":
        return "update"
    if workspace_status == "fast_generate":
        return "generate"

    # Unknown status — safest fallback is init (LLM re-audits everything).
    return "init"
