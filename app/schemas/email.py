"""Internal email models.

Models containing body text are deliberately kept separate from API response models.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ParsedEmail(BaseModel):
    """A locally parsed message used only during in-memory analysis."""

    model_config = ConfigDict(extra="forbid")

    message_id: str
    thread_id: str | None = None
    sender_display: str = "Unknown sender"
    sender_address: str | None = None
    sender_domain: str | None = None
    subject: str = "(No subject)"
    received_at: datetime
    body_text: str = Field(repr=False)
    label_ids: tuple[str, ...] = ()
    is_automated: bool = False
    is_promotional: bool = False
