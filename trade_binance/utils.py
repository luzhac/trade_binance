import csv
from base64 import urlsafe_b64encode
from datetime import timedelta, datetime
from email.mime.text import MIMEText

import pandas as pd


from datetime import datetime

import json
import logging
import os.path
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

dotenv_path="../.env"

log_dir = 'log'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
# Configure logging
logging.basicConfig(
    filename=os.path.join(log_dir, 'new.log'),
    level=logging.INFO,  # Set the logging level (can be changed to DEBUG, ERROR, etc.)
    format='%(asctime)s - %(levelname)s - %(message)s',  # Format the log messages
    datefmt='%Y-%m-%d %H:%M:%S',  # Format of the datetime in logs
    force=True  # Ensures this config is applied
)

def get_env_variable(name:str):
    load_dotenv(dotenv_path)
    value = os.getenv(name)
    if value is None:
        raise EnvironmentError(f"Environment variable {name} is missing")
    return value

def get_config(name:str):
    try:
        with open('../config/config.json') as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        return None
    try:
        value = config[name]
    except KeyError:
        raise EnvironmentError(f"Config variable {name} is missing")
    return value


def validate_config():
    try:
        with open('../config/config.json') as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        return None

def modify_minute(t1):
    t2 = t1
    v_m = t1.minute
    if v_m % 5 == 3:
        t2 = t1 + timedelta(minutes=2)
    if v_m % 5 == 4:
        t2 = t1 + timedelta(minutes=1)
    t3 = datetime(t2.year, t2.month, t2.day, t2.hour, t2.minute)
    return t3

def write_log(log_message, *args):
    log_message = f"{datetime.now()} {log_message} {' '.join(map(str, args))}\n"
    with open("../log/q_binance_api.log", "a") as file_object:
        file_object.write(log_message)


class GmailAPIWrapper:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(GmailAPIWrapper, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):  # Prevent re-initialization
            try:
                self.gmail_to = get_config('email_to')
            except Exception as e:
                print(f"Error reading gmail_to: {e}")
                self.gmail_to = ''

            self.gmail_from = ''
            self.SCOPES = ['https://www.googleapis.com/auth/gmail.send']
            self.last_send_email1 = ""
            self.last_send_email2 = ""
            self.last_send_email_time = ""

            self.initialized = True  # Mark as initialized

    def create_message(self, sender: str, to: str, subject: str, message_text: str):
        message = MIMEText(message_text)
        message['to'] = to
        message['from'] = sender
        message['subject'] = subject
        return {'raw': urlsafe_b64encode(message.as_bytes()).decode()}

    def send_message(self, service: str, user_id: str, message: str):
        try:
            message = (service.users().messages().send(userId=user_id, body=message).execute())
            return message
        except Exception as e:
            print(str(datetime.now()), 'An error occurred: %s' % e)

    def send_email(self, subject: str, content: str):
        try:
            if get_config('environment')=="development":
                return
        except Exception as e:
            print(f"Error environment: {e}")

        creds = None
        try:
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', self.SCOPES)
                    creds = flow.run_local_server(port=0, access_type='offline')
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
        except Exception as e:
            print(e)

        try:
            service = build('gmail', 'v1', credentials=creds)
            subject = subject + ' ' + str(datetime.now())
            message = self.create_message(self.gmail_from, self.gmail_to, subject, content)
            self.send_message(service, 'me', message)
        except HttpError as error:
            print(f'An error occurred: {error}')

    def send_email_not_duplicate(self, subject: str, content: str):
        text_to_send = subject
        if (text_to_send == self.last_send_email1 or text_to_send == self.last_send_email2) and (
                datetime.now() - self.last_send_email_time).total_seconds() < 600:
            pass
        else:
            self.send_email(subject, content)
            self.last_send_email2 = self.last_send_email1
            self.last_send_email1 = text_to_send
            self.last_send_email_time = datetime.now()
