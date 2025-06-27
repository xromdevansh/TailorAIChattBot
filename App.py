# TailorTalk - Fully Merged Streamlit App (Single File)

import streamlit as st
import datetime
import os
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dateparser.search import search_dates
from dotenv import load_dotenv

# Load environment
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'tailor-talk-agent-448fcde5f672.json'
CALENDAR_ID = 'primary'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('calendar', 'v3', credentials=credentials)

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
        return "⚠️ I couldn't understand the date/time. Please try something like 'Book on 20 July at 4 PM'."
    if is_available(start, end):
        create_appointment("Meeting via TailorTalk", start, end)
        return f"You're booked on {start.strftime('%A, %d %B %Y at %I:%M %p')}!"
    else:
        return f"You already have an appointment booked at {start.strftime('%A, %d %B %Y at %I:%M %p')}. Please choose another slot."

# Streamlit UI Setup
st.set_page_config(page_title="TailorTalk AI", page_icon="None", layout="centered")


st.title("TailorTalk - Book Appointments")
st.subheader("Let me schedule your meetings!!")

if "history" not in st.session_state:
    st.session_state.history = []

user_input = st.chat_input("Ask me to book an appointment with date/time...")

if user_input:
    st.session_state.history.append(("user", user_input))
    with st.spinner("Thinking..."):
        reply = handle_input(user_input)
    st.session_state.history.append(("bot", reply))

