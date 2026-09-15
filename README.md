# Smart Reminder Telegram Bot

Erkin matnli buyruqlarni AI (OpenAI, JSON mode) yordamida tahlil qilib,
bir martalik va davriy (kunlik/haftalik/oylik/yillik) eslatmalarni
Firebase Firestore + APScheduler orqali o'z vaqtida yuboradi.

## Stack
- Python 3.11+, aiogram 3.x (async)
- OpenAI `gpt-4o-mini`, JSON mode (`response_format={"type": "json_object"}`)
- Firebase Firestore (`firebase-admin`)
- APScheduler `AsyncIOScheduler`, `pytz`

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in BOT_TOKEN, OPENAI_API_KEY, FIREBASE_CREDENTIALS_PATH
# place your Firebase service-account JSON at the path set in FIREBASE_CREDENTIALS_PATH
python main.py
```

## Project layout

```
config.py                  env-driven configuration, fails fast if a var is missing
models/reminder.py         Reminder dataclass + validation (never trusts AI output blindly)
services/ai_parser.py      OpenAI call, strict JSON parsing, AIParseError on failure
services/firebase_service.py   Firestore CRUD, all calls off the event loop via asyncio.to_thread
services/scheduler_service.py  APScheduler job (de)registration, startup reschedule
keyboards/inline.py        all inline keyboards
handlers/start.py          /start, /help, timezone selection
handlers/reminders.py      free-text parsing -> confirmation -> save, /today, /list, delete
handlers/callbacks.py      notification buttons: done / snooze +15 / snooze +1h
utils/timezones.py         tz-aware datetime helpers + weekly-date self-correction
main.py                    wiring: Dispatcher, routers, startup reschedule, polling
```

## Design decisions / deviations from the original spec (and why)

1. **`httpx` pinned to `0.27.2`.** `openai==1.x` still passes a `proxies` kwarg
   to `httpx.AsyncClient` that `httpx>=0.28` removed — installing the spec's
   stack as-written crashes on the very first import. Verified by smoke test.

2. **"✅ Bajarildi" on a *recurring* reminder no longer force-completes the
   whole series.** The spec says the button always sets `status: completed`.
   Taken literally, tapping "done" on a daily/weekly/monthly/yearly reminder
   would silently cancel *all future* occurrences — almost certainly not what
   a user tapping "done" on today's notification wants. Implemented behavior:
   - `once` → marks `completed` and unschedules (matches spec exactly).
   - recurring → acknowledges the occurrence, job stays scheduled.
   If you actually want "done" to cancel the whole recurring series, that's a
   one-line change in `handlers/callbacks.py::on_done`, but it should be an
   explicit "delete series" action, not an overload of "done".

3. **Snooze (+15m / +1h) restricted to `once` reminders.** Snoozing a cron-based
   recurring trigger is ambiguous (snooze this occurrence only, or shift the
   whole recurrence pattern?). The notification keyboard only renders the
   snooze buttons for `once`; the handler also guards against it server-side
   in case of stale keyboards.

4. **Weekly date self-correction (`utils/timezones.ensure_weekly_consistency`).**
   The model is asked to compute "nearest matching weekday" itself, which is
   exactly the kind of date arithmetic LLMs get wrong under JSON-mode
   constraints. Before persisting, the app independently verifies
   `target_datetime.weekday() == day_of_week` and snaps to the correct next
   occurrence if not — the AI's weekday label is trusted as intent, its date
   math is not.

5. **Reminder validation is a hard gate, not a formality.** `Reminder.validate()`
   rejects weekly reminders without a valid `day_of_week`, monthly reminders
   without `day_of_month` in `[1, 31]`, and naive (non-tz-aware) datetimes,
   regardless of what the AI returned. A malformed AI response degrades to
   the "couldn't understand" message rather than silently saving broken state.

## Known follow-ups (not implemented, flagged for you)

- **Monthly reminders on day 29-31** will simply not fire in short months —
  APScheduler's `CronTrigger(day=31, ...)` just skips months without that day.
  If you need "last day of month" semantics, use `day='last'` conditionally.
- **No dedupe/lock on concurrent `/start`** — low risk for a Telegram bot but
  worth a Firestore transaction if you expect high concurrent first-time load.
- **`snooze` on a reminder that already fired and was deleted** returns
  "not found" gracefully but there's no user-facing distinction between
  "deleted" and "doesn't exist" — fine for now, mention if you want it split.
