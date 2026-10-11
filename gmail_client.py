import base64
import json
import os
import re
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import SCOPES, CREDENTIALS_FILE, TOKEN_FILE


def get_gmail_service():
    """Authenticate the user's Gmail account and return a Gmail API client."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, encoding="utf-8") as token:
            token_info = json.load(token)

        granted_scopes = set(token_info.get("scopes", []))
        if not granted_scopes and token_info.get("scope"):
            granted_scopes = set(token_info["scope"].split())

        if set(SCOPES).issubset(granted_scopes):
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        if not os.path.exists(CREDENTIALS_FILE):
            raise FileNotFoundError(
                f"{CREDENTIALS_FILE} was not found. "
                "Download your Google OAuth Desktop credentials first."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE,
            SCOPES,
        )
        creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send_email(service, to_email, subject, body):
    """Send one individual plain-text email."""
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    result = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )

    return result.get("id")


def list_delivery_failures(service, query="newer_than:30d"):
    """Return Gmail delivery-failure messages from the selected time window."""
    response = (
        service.users()
        .messages()
        .list(
            userId="me",
            q=f"in:anywhere {{from:mailer-daemon from:postmaster}} {query}",
        )
        .execute()
    )

    failures = []
    for item in response.get("messages", []):
        message = (
            service.users()
            .messages()
            .get(userId="me", id=item["id"], format="full")
            .execute()
        )
        headers = {
            header["name"].lower(): header["value"]
            for header in message.get("payload", {}).get("headers", [])
        }
        subject = headers.get("subject", "")
        text = _message_text(message.get("payload", {}))

        if not _looks_like_delivery_failure(subject, text):
            continue

        failures.append(
            {
                "message_id": item["id"],
                "received": headers.get("date", ""),
                "subject": subject,
                "recipients": _extract_email_addresses(text),
            }
        )

    return failures


def _message_text(payload):
    """Extract plain text from a Gmail message payload."""
    chunks = []
    body = payload.get("body", {})
    if body.get("data"):
        chunks.append(
            base64.urlsafe_b64decode(body["data"] + "==").decode(
                "utf-8", errors="replace"
            )
        )

    for part in payload.get("parts", []):
        chunks.append(_message_text(part))

    return "\n".join(chunk for chunk in chunks if chunk)


def _looks_like_delivery_failure(subject, text):
    content = f"{subject}\n{text}".lower()
    indicators = (
        "delivery status notification",
        "delivery incomplete",
        "address not found",
        "message not delivered",
        "user unknown",
        "mail delivery failed",
    )
    return any(indicator in content for indicator in indicators)


def _extract_email_addresses(text):
    return sorted(
        {
            address.lower()
            for address in re.findall(
                r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
                text,
            )
        }
    )
