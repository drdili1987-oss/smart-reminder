"""
Firestore access layer with hybrid in-memory fallback.

firebase-admin's Firestore client is synchronous. We wrap every call with
asyncio.to_thread so the aiogram event loop is never blocked.
"""
from __future__ import annotations

import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

from config import FIREBASE_CREDENTIALS_PATH, FIREBASE_CREDENTIALS_JSON, DEFAULT_TIMEZONE
from models.reminder import Reminder, ReminderStatus

logger = logging.getLogger(__name__)

_app = None
_db = None

try:
    if FIREBASE_CREDENTIALS_JSON:
        cred = credentials.Certificate(json.loads(FIREBASE_CREDENTIALS_JSON))
        _app = firebase_admin.initialize_app(cred)
        _db = firestore.client()
    elif os.path.exists(FIREBASE_CREDENTIALS_PATH):
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        _app = firebase_admin.initialize_app(cred)
        _db = firestore.client()
    else:
        logger.warning("Firebase credentials not found. Operating in in-memory mode.")
except Exception as exc:
    logger.error("Failed to initialize Firebase Admin SDK: %s", exc)
    _db = None

USERS_COLLECTION = "users"
REMINDERS_COLLECTION = "reminders"

# In-memory stores for seamless fallback if Firestore is unavailable
_in_memory_users: dict[int, dict] = {}
_in_memory_reminders: dict[str, Reminder] = {}


class FirebaseError(Exception):
    pass


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

async def upsert_user(user_id: int, username: Optional[str], first_name: str,
                       language: str = "uz", timezone_name: str = DEFAULT_TIMEZONE) -> None:
    existing = _in_memory_users.get(user_id, {})
    existing.update({
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "timezone": existing.get("timezone", timezone_name),
        "language": existing.get("language", language),
        "created_at": existing.get("created_at", datetime.now(timezone.utc).isoformat()),
    })
    _in_memory_users[user_id] = existing

    if _db is None:
        return

    def _write():
        try:
            ref = _db.collection(USERS_COLLECTION).document(str(user_id))
            doc = ref.get()
            if doc.exists:
                ref.update({
                    "username": username,
                    "first_name": first_name,
                })
            else:
                ref.set(existing)
        except Exception as exc:
            logger.error("Failed to upsert user %s in Firestore: %s", user_id, exc)

    await asyncio.to_thread(_write)


async def get_user(user_id: int) -> Optional[dict]:
    if _db is None:
        return _in_memory_users.get(user_id)

    def _read():
        try:
            doc = _db.collection(USERS_COLLECTION).document(str(user_id)).get()
            if doc.exists:
                data = doc.to_dict()
                _in_memory_users[user_id] = data
                return data
        except Exception as exc:
            logger.error("Failed to get user %s from Firestore: %s", user_id, exc)
        return _in_memory_users.get(user_id)

    return await asyncio.to_thread(_read)


async def set_user_timezone(user_id: int, timezone_name: str) -> None:
    if user_id in _in_memory_users:
        _in_memory_users[user_id]["timezone"] = timezone_name
    else:
        _in_memory_users[user_id] = {"timezone": timezone_name}

    if _db is None:
        return

    def _write():
        try:
            _db.collection(USERS_COLLECTION).document(str(user_id)).update({"timezone": timezone_name})
        except Exception as exc:
            logger.error("Failed to set timezone for user %s: %s", user_id, exc)

    await asyncio.to_thread(_write)


async def get_user_timezone(user_id: int) -> str:
    user = await get_user(user_id)
    if user and user.get("timezone"):
        return user["timezone"]
    return DEFAULT_TIMEZONE


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------

async def save_reminder(reminder: Reminder) -> None:
    reminder.validate()
    _in_memory_reminders[reminder.reminder_id] = reminder

    if _db is None:
        return

    def _write():
        try:
            _db.collection(REMINDERS_COLLECTION).document(reminder.reminder_id).set(
                reminder.to_firestore_dict()
            )
        except Exception as exc:
            logger.error("Failed to save reminder %s in Firestore: %s", reminder.reminder_id, exc)

    await asyncio.to_thread(_write)


async def update_reminder_status(reminder_id: str, status: ReminderStatus) -> None:
    if reminder_id in _in_memory_reminders:
        _in_memory_reminders[reminder_id].status = status

    if _db is None:
        return

    def _write():
        try:
            _db.collection(REMINDERS_COLLECTION).document(reminder_id).update(
                {"status": status.value}
            )
        except Exception as exc:
            logger.error("Failed to update status for reminder %s: %s", reminder_id, exc)

    await asyncio.to_thread(_write)


async def update_reminder_target_datetime(reminder_id: str, new_dt: datetime) -> None:
    if reminder_id in _in_memory_reminders:
        _in_memory_reminders[reminder_id].target_datetime = new_dt

    if _db is None:
        return

    def _write():
        try:
            _db.collection(REMINDERS_COLLECTION).document(reminder_id).update(
                {"target_datetime": new_dt.isoformat()}
            )
        except Exception as exc:
            logger.error("Failed to update target_datetime for reminder %s: %s", reminder_id, exc)

    await asyncio.to_thread(_write)


async def get_reminder(reminder_id: str) -> Optional[Reminder]:
    if _db is None:
        return _in_memory_reminders.get(reminder_id)

    def _read():
        try:
            doc = _db.collection(REMINDERS_COLLECTION).document(reminder_id).get()
            if doc.exists:
                r = Reminder.from_firestore_dict(doc.id, doc.to_dict())
                _in_memory_reminders[reminder_id] = r
                return r
        except Exception as exc:
            logger.error("Failed to get reminder %s from Firestore: %s", reminder_id, exc)
        return _in_memory_reminders.get(reminder_id)

    return await asyncio.to_thread(_read)


async def get_active_reminders_for_user(user_id: int) -> list[Reminder]:
    if _db is None:
        return [
            r for r in _in_memory_reminders.values()
            if r.user_id == user_id and r.status == ReminderStatus.ACTIVE
        ]

    def _read():
        try:
            query = (
                _db.collection(REMINDERS_COLLECTION)
                .where("user_id", "==", user_id)
                .where("status", "==", ReminderStatus.ACTIVE.value)
            )
            results = [Reminder.from_firestore_dict(d.id, d.to_dict()) for d in query.stream()]
            for r in results:
                _in_memory_reminders[r.reminder_id] = r
            return results
        except Exception as exc:
            logger.error("Failed to get active reminders from Firestore for user %s: %s", user_id, exc)
            return [
                r for r in _in_memory_reminders.values()
                if r.user_id == user_id and r.status == ReminderStatus.ACTIVE
            ]

    return await asyncio.to_thread(_read)


async def get_all_active_reminders() -> list[Reminder]:
    """Used on bot startup to rebuild the scheduler."""
    if _db is None:
        return [
            r for r in _in_memory_reminders.values()
            if r.status == ReminderStatus.ACTIVE
        ]

    def _read():
        try:
            query = _db.collection(REMINDERS_COLLECTION).where(
                "status", "==", ReminderStatus.ACTIVE.value
            )
            results = []
            for d in query.stream():
                try:
                    r = Reminder.from_firestore_dict(d.id, d.to_dict())
                    results.append(r)
                    _in_memory_reminders[r.reminder_id] = r
                except Exception:
                    logger.exception("Skipping malformed reminder doc %s", d.id)
            return results
        except Exception as exc:
            logger.error("Failed to fetch active reminders from Firestore: %s", exc)
            return [
                r for r in _in_memory_reminders.values()
                if r.status == ReminderStatus.ACTIVE
            ]

    return await asyncio.to_thread(_read)
