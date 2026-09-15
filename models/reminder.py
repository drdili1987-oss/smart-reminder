from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional


class ReminderType(str, Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class ReminderStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DELETED = "deleted"


VALID_WEEKDAYS = {
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
}

WEEKDAY_TO_CRON = {
    "monday": "mon", "tuesday": "tue", "wednesday": "wed",
    "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun",
}


@dataclass
class Reminder:
    user_id: int
    title: str
    type: ReminderType
    target_datetime: datetime  # timezone-aware, in the user's tz
    day_of_week: Optional[str] = None
    day_of_month: Optional[int] = None
    status: ReminderStatus = ReminderStatus.ACTIVE
    timezone: str = "Asia/Tashkent"
    category: str = "boshqa"  # "ish", "xarid", "sogliq", "shaxsiy", "boshqa"
    file_id: Optional[str] = None
    file_type: Optional[str] = None  # "photo" or "document"
    creator_name: Optional[str] = None
    reminder_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)

    def validate(self) -> None:
        """Raise ValueError on any structural inconsistency. Never trust AI output blindly."""
        if not self.title or not self.title.strip():
            raise ValueError("title is empty")

        if self.type == ReminderType.WEEKLY:
            if not self.day_of_week or self.day_of_week.lower() not in VALID_WEEKDAYS:
                raise ValueError(f"invalid day_of_week for weekly reminder: {self.day_of_week!r}")

        if self.type == ReminderType.MONTHLY:
            if self.day_of_month is None or not (1 <= self.day_of_month <= 31):
                raise ValueError(f"invalid day_of_month for monthly reminder: {self.day_of_month!r}")

        if self.target_datetime.tzinfo is None:
            raise ValueError("target_datetime must be timezone-aware")

    def to_firestore_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        d["status"] = self.status.value
        d["target_datetime"] = self.target_datetime.isoformat()
        d["created_at"] = self.created_at.isoformat()
        return d

    @staticmethod
    def from_firestore_dict(doc_id: str, data: dict) -> "Reminder":
        return Reminder(
            reminder_id=doc_id,
            user_id=data["user_id"],
            title=data["title"],
            type=ReminderType(data["type"]),
            target_datetime=datetime.fromisoformat(data["target_datetime"]),
            day_of_week=data.get("day_of_week"),
            day_of_month=data.get("day_of_month"),
            status=ReminderStatus(data.get("status", "active")),
            timezone=data.get("timezone", "Asia/Tashkent"),
            category=data.get("category", "boshqa"),
            file_id=data.get("file_id"),
            file_type=data.get("file_type"),
            creator_name=data.get("creator_name"),
            created_at=datetime.fromisoformat(data["created_at"])
            if isinstance(data.get("created_at"), str) else datetime.utcnow(),
        )
