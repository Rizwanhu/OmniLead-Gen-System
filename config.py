# Safety settings
DAILY_RUN_LIMIT = 50

# Delay between sends. Increase this if desired.
MIN_DELAY_SECONDS = 20
MAX_DELAY_SECONDS = 40

# Gmail OAuth scope. This allows the program to send mail.
# SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

LEADS_FILE = "leads.csv"
MESSAGES_FILE = "messages.csv"
SENT_LOG_FILE = "sent_log.csv"
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
