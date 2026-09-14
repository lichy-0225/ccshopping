"""Conversation state used by the explicit MVP agent pipeline."""

from pydantic import BaseModel, Field


class ConversationState(BaseModel):
    session_id: str
    category: str | None = None
    budget_max: float | None = None
    preferences: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    concern: str | None = None
    risk_level: str = "low"
    asked_fields: list[str] = Field(default_factory=list)
    candidates: list[str] = Field(default_factory=list)
    last_action: str | None = None
    messages: list[dict] = Field(default_factory=list)
    summary: str = ""
    current_goal: str | None = None
    concerns: list[str] = Field(default_factory=list)
    skin_profile: str | None = None
    zone_concerns: dict[str, list[str]] = Field(default_factory=dict)
    care_strategy: str | None = None
    selected_skus: list[str] = Field(default_factory=list)
    asked_questions: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    last_tool_results: list[dict] = Field(default_factory=list)

    def merge_unique(self, field: str, values: list[str]) -> None:
        current = list(getattr(self, field))
        for value in values:
            if value not in current:
                current.append(value)
        setattr(self, field, current)
