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


def _build_service_sync():
    """
    Builds the Google Calendar service synchronously.
    Must be run in a thread executor to avoid blocking the event loop.
    Returns None on failure.
    """
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        logging.warning(f"Google Calendar: key file not found at '{SERVICE_ACCOUNT_FILE}'")
        return None
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        logging.error(f"Google Calendar: failed to build service: {e}")
        return None


async def get_calendar_service():
    """Async wrapper around _build_service_sync to avoid blocking the event loop."""
    return await asyncio.to_thread(_build_service_sync)


async def get_occupied_slots(calendar_id: str, date_str: str):
    """
    Fetches events from Google Calendar for a specific date and returns occupied time ranges.
    date_str format: 'YYYY-MM-DD'
    Returns a list of tuples: [('14:00', '15:00'), ...]
    ALWAYS returns [] on any error so the bot never crashes when Google is unavailable.
    """
    try:
        service = await get_calendar_service()
        if not service:
            return []
    except Exception as e:
        logging.warning(f"Google Calendar: skipping occupied slots (service unavailable): {e}")
        return []

    try:
        time_min = f"{date_str}T00:00:00Z"
        time_max = f"{date_str}T23:59:59Z"

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
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            if start and end and 'T' in start:
                start_time = start.split('T')[1][:5]
                end_time = end.split('T')[1][:5]
                occupied.append((start_time, end_time))
            # All-day events are skipped

        return occupied

    except Exception as e:
        logging.error(f"Google Calendar: error in get_occupied_slots: {e}")
        return []


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
