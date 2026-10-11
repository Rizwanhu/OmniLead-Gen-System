import argparse
import csv
import os
import random
import re
import time
from datetime import datetime

from config import (
    DAILY_RUN_LIMIT,
    MIN_DELAY_SECONDS,
    MAX_DELAY_SECONDS,
    LEADS_FILE,
    MESSAGES_FILE,
    SENT_LOG_FILE,
)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def read_csv(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing file: {path}")

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_data():
    leads = read_csv(LEADS_FILE)
    messages = read_csv(MESSAGES_FILE)

    lead_by_id = {}
    for lead in leads:
        lead_id = (lead.get("lead_id") or "").strip()
        if not lead_id:
            continue
        lead_by_id[lead_id] = lead

    message_by_id = {}
    for msg in messages:
        lead_id = (msg.get("lead_id") or "").strip()
        if not lead_id:
            continue
        message_by_id[lead_id] = msg

    return lead_by_id, message_by_id


def load_sent_recipients():
    if not os.path.exists(SENT_LOG_FILE):
        return set()

    with open(SENT_LOG_FILE, "r", encoding="utf-8-sig", newline="") as f:
        return {
            (
                (row.get("lead_id") or "").strip(),
                (row.get("email") or "").strip().lower(),
            )
            for row in csv.DictReader(f)
            if row.get("status") == "sent"
        }


def append_log(lead_id, email, status, message_id="", error=""):
    exists = os.path.exists(SENT_LOG_FILE)

    with open(SENT_LOG_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "lead_id",
                "email",
                "status",
                "message_id",
                "error",
            ],
        )

        if not exists:
            writer.writeheader()

        writer.writerow(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "lead_id": lead_id,
                "email": email,
                "status": status,
                "message_id": message_id,
                "error": error,
            }
        )


def personalize(text, lead):
    """Replace {column_name} placeholders with values from the lead."""
    class SafeDict(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    return text.format_map(SafeDict(lead))


def build_messages():
    leads, messages = load_data()
    sent_recipients = load_sent_recipients()

    jobs = []

    for lead_id, lead in leads.items():
        email = (lead.get("email") or "").strip()

        if not email or not EMAIL_RE.match(email):
            print(f"[SKIP] {lead_id}: invalid/missing email")
            continue

        if (lead_id, email.lower()) in sent_recipients:
            continue

        msg = messages.get(lead_id)

        if not msg:
            print(f"[SKIP] {lead_id}: no message found in messages.csv")
            continue

        subject = personalize(msg.get("subject", ""), lead).strip()
        body = personalize(msg.get("body", ""), lead).strip()

        if not subject or not body:
            print(f"[SKIP] {lead_id}: empty subject/body")
            continue

        jobs.append(
            {
                "lead_id": lead_id,
                "name": lead.get("name", ""),
                "email": email,
                "company": lead.get("company", ""),
                "subject": subject,
                "body": body,
            }
        )

    return jobs


def preview(jobs):
    print("\n========== PREVIEW ==========\n")

    if not jobs:
        print("No messages ready.")
        return

    for i, job in enumerate(jobs, start=1):
        print(f"--- {i} ---")
        print(f"Lead ID : {job['lead_id']}")
        print(f"To      : {job['email']}")
        print(f"Name    : {job['name']}")
        print(f"Company : {job['company']}")
        print(f"Subject : {job['subject']}")
        print("Body:")
        print(job["body"])
        print()


def authenticate_only():
    from gmail_client import get_gmail_service

    print("Authenticating Gmail...")
    service = get_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    print(f"Authenticated Gmail account: {profile.get('emailAddress')}")


def check_bounces():
    from gmail_client import get_gmail_service, list_delivery_failures

    print("Checking Gmail for delivery failures from the last 30 days...")
    service = get_gmail_service()
    failures = list_delivery_failures(service)

    sent_records = {}
    recorded_bounces = set()
    if os.path.exists(SENT_LOG_FILE):
        with open(SENT_LOG_FILE, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("status") == "sent":
                    sent_records[row.get("email", "").strip().lower()] = row
                elif row.get("status") == "bounced":
                    recorded_bounces.add(
                        (
                            row.get("message_id", ""),
                            row.get("email", "").strip().lower(),
                        )
                    )

    matched = []
    for failure in failures:
        for email in failure["recipients"]:
            record = sent_records.get(email)
            bounce_key = (failure["message_id"], email)
            if record and bounce_key not in recorded_bounces:
                matched.append((record, failure))
                append_log(
                    record.get("lead_id", ""),
                    record.get("email", ""),
                    "bounced",
                    message_id=failure["message_id"],
                    error=failure["subject"],
                )
                recorded_bounces.add(bounce_key)

    if not matched:
        print("No delivery failures matched successfully sent leads.")
        return

    print(f"\nDelivery failures found: {len(matched)}")
    for record, failure in matched:
        print(
            f"  BOUNCED: lead {record.get('lead_id')} "
            f"{record.get('email')} — {failure['subject']}"
        )
    print("\nThe original sends were kept. These leads were not blocked or deleted.")


def send_jobs(jobs, selected_ids=None):
    from gmail_client import get_gmail_service, send_email

    if selected_ids:
        jobs = [j for j in jobs if j["lead_id"] in selected_ids]

    if not jobs:
        print("Nothing to send.")
        return

    if len(jobs) > DAILY_RUN_LIMIT:
        print(
            f"Safety limit: {DAILY_RUN_LIMIT} messages per run. "
            f"Found {len(jobs)} ready messages."
        )
        print("Run a smaller selection with --ids.")
        return

    print(f"Ready to send {len(jobs)} separate email(s).")
    print("The program will wait between messages.")

    confirm = input("Type SEND to continue: ").strip()
    if confirm != "SEND":
        print("Cancelled.")
        return

    service = get_gmail_service()

    successful = 0

    for index, job in enumerate(jobs, start=1):
        print(
            f"\n[{index}/{len(jobs)}] "
            f"Sending to {job['email']}..."
        )

        try:
            message_id = send_email(
                service,
                job["email"],
                job["subject"],
                job["body"],
            )

            append_log(
                job["lead_id"],
                job["email"],
                "sent",
                message_id=message_id,
            )

            successful += 1
            print(f"  SENT. Gmail message ID: {message_id}")

        except Exception as exc:
            append_log(
                job["lead_id"],
                job["email"],
                "failed",
                error=str(exc),
            )
            print(f"  FAILED: {exc}")

        if index < len(jobs):
            delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
            print(f"Waiting {delay} seconds...")
            time.sleep(delay)

    print(f"\nFinished. Successful sends: {successful}/{len(jobs)}")
    print("Run `python main.py --check-bounces` later to find delayed failures.")


def main():
    parser = argparse.ArgumentParser(
        description="Send separate personalized emails through Gmail."
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--send", action="store_true")
    mode.add_argument("--auth-test", action="store_true")
    mode.add_argument("--check-bounces", action="store_true")

    parser.add_argument(
        "--ids",
        help="Comma-separated lead IDs, e.g. 001,003,005",
    )

    args = parser.parse_args()

    if args.auth_test:
        authenticate_only()
        return
    if args.check_bounces:
        check_bounces()
        return

    jobs = build_messages()

    if args.preview or not args.send:
        preview(jobs)
        return

    selected_ids = None
    if args.ids:
        selected_ids = {
            item.strip()
            for item in args.ids.split(",")
            if item.strip()
        }

    send_jobs(jobs, selected_ids=selected_ids)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
