import streamlit as st
import datetime
import os
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dateparser.search import search_dates

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

# ------------------ UTIL FUNCTIONS ------------------

def extract_datetime_range(text):
    results = search_dates(
        text,
        settings={
            'PREFER_DATES_FROM': 'future',
            'TIMEZONE': 'Asia/Kolkata',
            'RETURN_AS_TIMEZONE_AWARE': False,
            'DATE_ORDER': 'DMY'
        }
    )
    if not results:
        return None, None
    parsed = results[0][1]
    start_time = parsed
    end_time = parsed + datetime.timedelta(minutes=DEFAULT_DURATION_MINUTES)
    return start_time, end_time

def is_available(start_time, end_time):
    events = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat() + 'Z',
        timeMax=end_time.isoformat() + 'Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return len(events.get('items', [])) == 0

def get_events_between(start_time, end_time):
    events = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat() + 'Z',
        timeMax=end_time.isoformat() + 'Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events.get('items', [])

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
    now = datetime.datetime.now()

    if "next week" in lower or "coming week" in lower:
        today = datetime.datetime.now()
        days_ahead = 7 - today.weekday()  # days until next Monday
        start = today + datetime.timedelta(days=days_ahead)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + datetime.timedelta(days=7)

    elif "right now" in lower:
        start = now
        end = now + datetime.timedelta(minutes=30)

    elif "tomorrow" in lower:
        start = now + datetime.timedelta(days=1)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + datetime.timedelta(days=1)

    else:
        start, end = extract_datetime_range(user_input)
        if not start or not end:
            return "❓ I couldn't understand the time. Try something like 'Next Monday 3PM'."

    events = get_events_between(start, end)

    if events:
        seen = set()
        event_lines = []
        for e in events:
            start_time = e['start'].get('dateTime', e['start'].get('date'))
            event_key = (e['summary'], start_time)
            if event_key not in seen:
                seen.add(event_key)
                event_lines.append(f"📅 {e['summary']} at {start_time}")
        return "Here’s what’s on your calendar:\n" + "\n".join(event_lines)
    else:
        return "✅ You're totally free during that time!"


def handle_booking(user_input):
    start, end = extract_datetime_range(user_input)
    if not start or not end:
        return "🕵️‍♂️ Hmm... I couldn’t get the date/time. Try something like 'Book 5th July 3PM'."
    if is_available(start, end):
        create_appointment("Meeting via TailorTalk", start, end)
        return f"🎉 You're locked in for {start.strftime('%A, %d %B %Y at %I:%M %p')}!"
    else:
        return f"🚫 That time's already taken: {start.strftime('%A, %d %B %Y at %I:%M %p')}. Try something else."

def handle_input(user_input):
    lower = user_input.lower()

    # Keywords that suggest booking
    is_booking = any(kw in lower for kw in [
        "book", "schedule", "make an appointment", "set up"
    ])

    # Keywords that suggest checking availability or listing
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
        # fallback: try to book by default
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
user_input = st.chat_input("Type something like 'Next Monday 5PM' or 'Am I booked tomorrow?'")
if user_input:
    st.session_state.history.append(("user", user_input))
    with st.spinner("🧠 Thinking like a calendar ninja..."):
        reply = handle_input(user_input)
    st.session_state.history.append(("bot", reply))

# Display Chat
st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
for sender, msg in st.session_state.history:
    msg_class = "user-msg" if sender == "user" else "bot-msg"
    st.markdown(f"<div class='{msg_class}'>{msg}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
