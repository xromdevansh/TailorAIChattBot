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

    if parsed.hour == 0 and parsed.minute == 0 and not any(word in lowered_text for word in ["am", "pm", "morning", "afternoon", "evening", "night"]):
        parsed = parsed.replace(hour=9, minute=0)

    parsed = parsed.replace(tzinfo=IST)

    start_time = parsed
    end_time = parsed + datetime.timedelta(minutes=DEFAULT_DURATION_MINUTES)
    return start_time, end_time

def is_available(start_time, end_time):
    events = get_events_between(start_time, end_time)
    return len(events) == 0

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
        day_match = re.search(r"(on\\s)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", lower)
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
                readable_time = datetime.datetime.fromisoformat(start_time.replace("Z", "")).astimezone(IST).strftime('%A, %d %B %Y at %I:%M %p')
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

# ------------------ UI ------------------

st.set_page_config(page_title="TailorTalk ✨", page_icon="🧠", layout="centered")

# CSS
st.markdown("""
    <style>
    .stApp { font-family: 'Segoe UI', sans-serif; background-color: #fefefe; }
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-top: 2rem;
        padding: 1rem 1rem;
    }
    .user-msg {
        background: linear-gradient(120deg, #a1ffce, #faffd1);
        color: #111;
        padding: 12px 18px;
        border-radius: 20px 20px 0px 20px;
        align-self: flex-end;
        max-width: 80%;
        font-size: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .bot-msg {
        background: #ffffffcc;
        color: #222;
        padding: 12px 18px;
        border-radius: 20px 20px 20px 0px;
        align-self: flex-start;
        max-width: 80%;
        font-size: 15px;
        border-left: 4px solid #007acc;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .title-style {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a1a1a;
        background: linear-gradient(to right, #007acc, #00c3ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='title-style'>TailorTalk 🤖</h1>", unsafe_allow_html=True)
st.caption("Your AI-powered scheduling buddy. Just tell me when you're free!")

# Session
if "history" not in st.session_state:
    st.session_state.history = []

# Chat
user_input = st.chat_input("Type something like 'Next Monday 5PM' or 'Am I booked tomorrow?" )
if user_input:
    if "yes" in user_input.lower() and st.session_state.get("pending_booking"):
        start, end = st.session_state.pending_booking
        create_appointment("Meeting via TailorTalk", start, end)
        st.session_state.pending_booking = None
        reply = f"✅ Your appointment is confirmed for {start.strftime('%A, %d %B %Y at %I:%M %p')}!"
    else:
        reply = handle_input(user_input)

    st.session_state.history.append(("user", user_input))
    st.session_state.history.append(("bot", reply))

# Display Chat
st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
for sender, msg in st.session_state.history:
    msg_class = "user-msg" if sender == "user" else "bot-msg"
    st.markdown(f"<div class='{msg_class}'>{msg}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
