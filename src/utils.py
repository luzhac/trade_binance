import json
import logging
import os.path
import base64





from dotenv import load_dotenv

dotenv_path="../.env"

# Configure logging
logging.basicConfig(
    filename='../log/new.log',  # Path to the log file
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
    with open('../config/config.json') as config_file:
        config = json.load(config_file)
    try:
        value = config[name]
    except KeyError:
        raise EnvironmentError(f"Config variable {name} is missing")
    return value


# Updated write_log function
def write_log(txt_log: str, *args):
    # Format the message
    log_message = txt_log + ' ' + ' '.join(map(str, args))
    # Log the message with INFO level
    logging.info(log_message)


class GmailSender:
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']

    def __init__(self, credentials_path='../config/credentials.json', token_path='../config/token.json'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None


    def _authenticate(self):

        """Authenticate the user and create a Gmail API service."""


    def create_message(self, to, subject, body):
        """Create a MIMEText email message."""


    def send_email(self, to, subject, body):
        """Send an email message via Gmail API."""

