import streamlit as st
import datetime
import os
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dateparser.search import search_dates
import re
import calendar
from pytz import timezone

# Load secrets
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_INFO = st.secrets["gcp_service_account"]
credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO, scopes=SCOPES)
service = build('calendar', 'v3', credentials=credentials)
CALENDAR_ID = 'primary'

DEFAULT_DURATION_MINUTES = 30
IST = timezone("Asia/Kolkata")

# ------------------ UTIL FUNCTIONS ------------------

def extract_datetime_range(text):
    lowered_text = text.lower()
    results = search_dates(
        lowered_text,
        settings={
            'PREFER_DATES_FROM': 'future',
            'TIMEZONE': 'Asia/Kolkata',
            'RETURN_AS_TIMEZONE_AWARE': False,
            'DATE_ORDER': 'DMY'
        }
    )
    if not results:
        return None, None

    parsed_text, parsed = results[0]

    if "afternoon" in lowered_text:
        parsed = parsed.replace(hour=14, minute=0)
    elif "evening" in lowered_text:
        parsed = parsed.replace(hour=18, minute=0)
    elif "morning" in lowered_text:
        parsed = parsed.replace(hour=9, minute=0)
    elif "night" in lowered_text:
        parsed = parsed.replace(hour=21, minute=0)

    parsed = parsed.replace(tzinfo=IST)

    start_time = parsed
    end_time = parsed + datetime.timedelta(minutes=DEFAULT_DURATION_MINUTES)
    return start_time, end_time


def is_available(start_time, end_time):
    events = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat(),
        timeMax=end_time.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return len(events.get('items', [])) == 0


def get_events_between(start_time, end_time):
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=IST)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=IST)

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat(),
        timeMax=end_time.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])


def create_appointment(summary, start_time, end_time):
    event = {
        'summary': summary,
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
    }
    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created_event.get('htmlLink')

# ------------------ HANDLERS ------------------

def handle_query(user_input):
    lower = user_input.lower()
    now = datetime.datetime.now(IST)

    if "next week" in lower or "coming week" in lower:
        today = now
        days_ahead = 7 - today.weekday()
        start = today + datetime.timedelta(days=days_ahead)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + datetime.timedelta(days=7)

    elif "tomorrow" in lower:
        start = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + datetime.timedelta(days=1)

    else:
        day_match = re.search(r"(on\s)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", lower)
        if day_match:
            target_day = list(calendar.day_name).index(day_match.group(2).capitalize())
            today = now
            days_ahead = (target_day - today.weekday() + 7) % 7
            start = today + datetime.timedelta(days=days_ahead)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + datetime.timedelta(days=1)
        else:
            start, _ = extract_datetime_range(user_input)
            if not start:
                return "❓ I couldn't understand the time. Try saying something like 'Next Monday 3PM'."
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + datetime.timedelta(days=1)

    events = get_events_between(start, end)

    if events:
        seen = set()
        event_lines = []
        for e in events:
            summary = e.get('summary', 'No Title')
            start_time = e['start'].get('dateTime', e['start'].get('date'))
            key = f"{summary}-{start_time}"
            if key not in seen:
                seen.add(key)
                readable_time = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00")).astimezone(IST).strftime('%A, %d %B %Y at %I:%M %p')
                event_lines.append(f"📅 {summary} at {readable_time}")
        return "Here’s what’s on your calendar:\n" + "\n".join(event_lines)
    else:
        return "✅ You're totally free during that time!"


def handle_booking(user_input):
    start, end = extract_datetime_range(user_input)
    if not start or not end:
        return "🕵️‍♂️ Hmm... I couldn’t get the date/time. Try something like 'Book 5th July 3PM'."
    if is_available(start, end):
        readable_time = start.strftime('%A, %d %B %Y at %I:%M %p')
        st.session_state.pending_booking = (start, end)
        return f"🤖 I found a free slot on {readable_time}. Should I book it for you? (Type 'yes' to confirm)"
    else:
        return f"🚫 That time's already taken: {start.strftime('%A, %d %B %Y at %I:%M %p')}. Try something else."


def handle_input(user_input):
    lower = user_input.lower()

    is_booking = any(kw in lower for kw in [
        "book", "schedule", "make an appointment", "set up"
    ])

    is_checking = any(kw in lower for kw in [
        "do i have", "am i free", "anything booked", "appointment",
        "what's scheduled", "is anything", "free on", "available",
        "calendar", "do i", "check", "show me"
    ])

    if is_booking:
        return handle_booking(user_input)
    elif is_checking:
        return handle_query(user_input)
    else:
        return handle_booking(user_input)
