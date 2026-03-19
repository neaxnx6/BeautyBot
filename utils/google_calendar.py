import os
import logging
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Path to your service account key file
SERVICE_ACCOUNT_FILE = 'google_key.json'
# Full access scope: read + write
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Builds the Google Calendar service. Returns None if key file missing."""
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        logging.warning(f"Google Calendar: key file '{SERVICE_ACCOUNT_FILE}' not found, sync disabled.")
        return None
    
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        logging.error(f"Google Calendar: failed to build service: {e}")
        return None

async def get_occupied_slots(calendar_id: str, date_str: str):
    """
    Fetches events from Google Calendar for a specific date and returns occupied time ranges.
    date_str format: 'YYYY-MM-DD'
    Returns a list of tuples: [('14:00', '15:00'), ...]
    """
    service = get_calendar_service()
    if not service:
        return []

    try:
        # Define start and end of the day in RFC3339 format
        time_min = f"{date_str}T00:00:00Z"
        time_max = f"{date_str}T23:59:59Z"

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        occupied = []

        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            # Extract HH:mm
            if 'T' in start:
                start_time = start.split('T')[1][:5]
                end_time = end.split('T')[1][:5]
                occupied.append((start_time, end_time))
            else:
                # All-day event
                occupied.append(('00:00', '23:59'))
                
        return occupied

    except HttpError as error:
        print(f"An error occurred: {error}")
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
    Returns event ID on success, None on failure.
    All errors are caught silently - Google failure never blocks booking.
    """
    service = get_calendar_service()
    if not service:
        return None
    
    try:
        # Parse 'DD.MM' + current/next year
        now = datetime.now()
        day, month = map(int, date_str.split('.'))
        year = now.year
        if month < now.month:
            year += 1
        
        hour, minute = map(int, time_str.split(':'))
        
        start_dt = datetime(year, month, day, hour, minute)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        
        # Format as RFC3339 in Moscow time (UTC+3)
        def to_rfc3339(dt):
            return dt.strftime('%Y-%m-%dT%H:%M:%S+03:00')
        
        event = {
            'summary': f'{client_name} — {service_name}',
            'description': f'Запись через Telegram-бот. Услуга: {service_name}',
            'start': {'dateTime': to_rfc3339(start_dt), 'timeZone': 'Europe/Moscow'},
            'end': {'dateTime': to_rfc3339(end_dt), 'timeZone': 'Europe/Moscow'},
        }
        
        created = service.events().insert(calendarId=calendar_id, body=event).execute()
        logging.info(f"Google Calendar: created event '{event['summary']}' at {to_rfc3339(start_dt)}")
        return created.get('id')
    
    except Exception as e:
        logging.warning(f"Google Calendar: failed to create event: {e}")
        return None


if __name__ == "__main__":
    import asyncio
    async def test():
        slots = await get_occupied_slots('rikouvens7@gmail.com', '2026-03-12')
        print(f"Occupied slots: {slots}")
    asyncio.run(test())
