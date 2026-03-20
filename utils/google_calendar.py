import os
import asyncio
import logging
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account

SCOPES = ['https://www.googleapis.com/auth/calendar']

# Build absolute path to google_key.json relative to this file's parent directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'google_key.json')

# Module-level cache: build the service once, reuse it forever
_service_cache = None


def _build_service_sync():
    """
    Builds the Google Calendar service synchronously.
    Uses a module-level cache so we only pay the `build()` cost once.
    """
    global _service_cache
    if _service_cache is not None:
        return _service_cache

    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        logging.warning(f"Google Calendar: key file not found at '{SERVICE_ACCOUNT_FILE}'")
        return None

    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        # static_discovery=False avoids downloading the discovery document from Google
        _service_cache = build('calendar', 'v3', credentials=creds, static_discovery=False)
        logging.info("Google Calendar: service built and cached successfully.")
        return _service_cache
    except Exception as e:
        logging.error(f"Google Calendar: failed to build service: {e}")
        return None


async def get_calendar_service():
    """Async wrapper — runs the sync build in a thread, returns cached result fast on repeat calls."""
    return await asyncio.to_thread(_build_service_sync)


async def get_occupied_slots_range(calendar_id: str, date_from: str, date_to: str) -> list:
    """
    Fetches ALL events from Google Calendar in a date range with ONE API call.
    date_from / date_to format: 'YYYY-MM-DD'
    Returns a list of (date_str, start_time, end_time) tuples,
    e.g. [('2026-03-25', '14:00', '15:00'), ...]
    ALWAYS returns [] on any error.
    """
    try:
        service = await get_calendar_service()
        if not service:
            return []
    except Exception as e:
        logging.warning(f"Google Calendar: service unavailable: {e}")
        return []

    try:
        time_min = f"{date_from}T00:00:00Z"
        time_max = f"{date_to}T23:59:59Z"

        def _fetch():
            return service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

        events_result = await asyncio.to_thread(_fetch)
        events = events_result.get('items', [])
        occupied = []

        for event in events:
            start = event['start'].get('dateTime', '')
            end = event['end'].get('dateTime', '')
            if 'T' not in start:
                # All-day event — skip (it blocks the whole day but we handle this separately)
                continue
            # start = '2026-03-25T14:00:00+03:00'
            date_part = start.split('T')[0]          # '2026-03-25'
            start_time = start.split('T')[1][:5]     # '14:00'
            end_time = end.split('T')[1][:5]         # '15:00'
            occupied.append((date_part, start_time, end_time))

        return occupied

    except Exception as e:
        logging.error(f"Google Calendar: error fetching range {date_from}–{date_to}: {e}")
        return []


# Keep backward-compatible single-date version (used in some places)
async def get_occupied_slots(calendar_id: str, date_str: str) -> list:
    """
    Single-date wrapper around get_occupied_slots_range.
    Returns [('HH:MM', 'HH:MM'), ...] for the given date.
    """
    results = await get_occupied_slots_range(calendar_id, date_str, date_str)
    return [(s, e) for _, s, e in results]


async def create_calendar_event(
    calendar_id: str,
    date_str: str,       # 'DD.MM' format, e.g. '15.03'
    time_str: str,       # 'HH:MM' format, e.g. '14:00'
    duration_minutes: int,
    client_name: str,
    service_name: str
):
    """
    Creates an event in Google Calendar when a client books via the bot.
    Raises Exception on failure so the caller can notify the admin.
    """
    service = await get_calendar_service()
    if not service:
        raise Exception(f"Не удалось подключиться к Google Calendar (файл ключа: {SERVICE_ACCOUNT_FILE})")

    now = datetime.now()
    day, month = map(int, date_str.split('.'))
    year = now.year
    if month < now.month:
        year += 1

    hour, minute = map(int, time_str.split(':'))
    start_dt = datetime(year, month, day, hour, minute)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    def to_rfc3339(dt):
        return dt.strftime('%Y-%m-%dT%H:%M:%S+03:00')

    event = {
        'summary': f'{client_name} — {service_name}',
        'description': f'Запись через Telegram-бот. Услуга: {service_name}',
        'start': {'dateTime': to_rfc3339(start_dt), 'timeZone': 'Europe/Moscow'},
        'end': {'dateTime': to_rfc3339(end_dt), 'timeZone': 'Europe/Moscow'},
    }

    def _insert():
        return service.events().insert(calendarId=calendar_id, body=event).execute()

    try:
        created = await asyncio.to_thread(_insert)
        logging.info(f"Google Calendar: created event '{event['summary']}' at {to_rfc3339(start_dt)}")
        return created.get('id')
    except Exception as e:
        raise Exception(f"Ошибка при создании события в Google Calendar: {e}")
