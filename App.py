# TailorTalk - ✨ Unique Styled AI Appointment Bot

import streamlit as st
import datetime
import os
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dateparser.search import search_dates

# Secrets from Streamlit Cloud
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_INFO = st.secrets["gcp_service_account"]
credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO, scopes=SCOPES)
service = build('calendar', 'v3', credentials=credentials)
CALENDAR_ID = 'primary'

# Utils
DEFAULT_DURATION_MINUTES = 30

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

def create_appointment(summary, start_time, end_time):
    event = {
        'summary': summary,
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
    }
    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created_event.get('htmlLink')

def handle_input(user_input):
    start, end = extract_datetime_range(user_input)
    if not start or not end:
        return "🕵️‍♂️ Hmm... I couldn’t get the date/time. Try saying something like 'Book 5th July 3PM'."
    if is_available(start, end):
        create_appointment("Meeting via TailorTalk", start, end)
        return f"🎉 You're locked in for {start.strftime('%A, %d %B %Y at %I:%M %p')}!"
    else:
        return f"🚫 That time's already taken! Try something else."

# 🌈 Custom Styling
st.set_page_config(page_title="TailorTalk ✨", page_icon="🧠", layout="centered")
st.markdown("""
    <style>
    body { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%) }
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

# 🧵 App Title & Instructions
st.markdown("<h1 class='title-style'>TailorTalk 🤖</h1>", unsafe_allow_html=True)
st.caption("Your AI-powered scheduling buddy. Just tell me when you're free!")

# Session State
if "history" not in st.session_state:
    st.session_state.history = []

# 💬 Chat Input
user_input = st.chat_input("Type something like 'Next Monday 5PM'...")
if user_input:
    st.session_state.history.append(("user", user_input))
    with st.spinner("🧠 Thinking like a calendar ninja..."):
        reply = handle_input(user_input)
    st.session_state.history.append(("bot", reply))

# 🔄 Display Chat
st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
for sender, msg in st.session_state.history:
    msg_class = "user-msg" if sender == "user" else "bot-msg"
    st.markdown(f"<div class='{msg_class}'>{msg}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
