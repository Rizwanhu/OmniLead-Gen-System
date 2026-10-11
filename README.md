# Gmail Personalized Sender

A small local Python app that sends **one separate Gmail message per lead**.

## Features

- Reads leads from `leads.csv`
- Reads a separate personalized message for each lead from `messages.csv`
- Matches records using `lead_id`
- Supports `{name}`, `{company}`, `{website}`, etc. placeholders
- Gmail OAuth2 authentication
- First run opens Google login/consent
- Saves OAuth token locally in `token.json`
- `DRY_RUN=true` by default: no email is sent
- `--preview` shows exactly what would be sent
- `--send` sends messages
- `sent_log.csv` prevents accidental duplicate sends to the same lead email
- Daily safety cap and delay between messages
- Invalid/missing emails are skipped
- Errors are logged
- No third-party paid email service is required

## Important

Use this for legitimate, targeted outreach and recipients you are allowed to contact. Do not use it to evade Gmail anti-spam systems or send unsolicited high-volume campaigns.

Google can limit or block sending when an account sends too much or generates bounces. A normal Gmail account has a published limit of about 500 outgoing messages/day, but this project deliberately uses a much lower configurable cap.

## 1. Install Python

Use Python 3.10+.

Check:

    python --version

## 2. Create a virtual environment (Windows PowerShell)

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1

If PowerShell blocks activation, you can instead run:

    .\.venv\Scripts\python.exe -m pip install -r requirements.txt

## 3. Install packages

    pip install -r requirements.txt

## 4. Create Google OAuth credentials

1. Open Google Cloud Console.
2. Create a new project.
3. Enable **Gmail API**.
4. Configure Google Auth Platform / OAuth consent.
5. Create an OAuth Client ID.
6. Choose **Desktop app**.
7. Download the JSON.
8. Rename it to:

    credentials.json

9. Put `credentials.json` in this project folder.

NEVER upload credentials.json or token.json to GitHub.

## 5. Put your leads in leads.csv

Example:

    lead_id,name,email,company,website
    001,Ahmed,ahmed@example.com,ABC Dental,https://example.com
    002,Sarah,sarah@example.com,XYZ Clinic,https://example.org

## 6. Put individual messages in messages.csv

Each row corresponds to one lead_id:

    lead_id,subject,body
    001,Quick idea for ABC Dental,"Hi {name},

I checked out {company} and wanted to share a quick idea.

Would you be open to a short chat?

Best,
Rizwan"
    002,A quick idea for XYZ Clinic,"Hi {name},

I had a look at {company}. I think there may be a simple automation opportunity worth discussing.

Best,
Rizwan"

The `{name}`, `{company}`, `{website}` values are automatically replaced using leads.csv.

You can also write a completely different message for every lead. Nothing requires the messages to use the same template.

## 7. Test Gmail authentication

Run:

    python main.py --auth-test

`--preview` does not connect to Gmail or send email. The first
`--auth-test` run will ask you to authorize the Gmail account.

A browser window should open. Sign in and grant the requested Gmail permissions.

After successful authorization, `token.json` is created.

If the app requests new permissions later, it automatically starts OAuth again
when the existing `token.json` does not contain all required scopes.

## 8. Preview before sending

    python main.py --preview

Running `python main.py` with no mode also uses the safe preview mode.

This prints every message that would be sent.

## 9. Send

Only after checking the preview:

    python main.py --send

The default safety cap is 50 messages per run.

You can change it in `config.py`, but do not use the program to bypass Gmail limits.

## 10. Prevent duplicates

After a successful send, the program writes the lead to:

    sent_log.csv

If you run `--send` again, a lead is skipped only when that same lead ID was
already sent successfully to the same email address. If you update a lead's
email address in `leads.csv`, the new address is treated as unsent so it can
receive the message.

To intentionally send again to a lead, remove that lead's successful row from `sent_log.csv`.

## Files

    gmail_personalized_sender/
    ├── main.py
    ├── gmail_client.py
    ├── config.py
    ├── requirements.txt
    ├── leads.csv
    ├── messages.csv
    ├── sent_log.csv
    ├── credentials.json       <- YOU ADD THIS
    ├── token.json             <- CREATED AFTER LOGIN
    └── .gitignore

## Commands

Preview:

    python main.py --preview

Send:

    python main.py --send

Send only selected lead IDs:

    python main.py --send --ids 001,003

Test Gmail authentication without sending:

    python main.py --auth-test

Check for delayed Gmail delivery failures:

    python main.py --check-bounces

Gmail can accept a message first and report an invalid or unavailable address
later. The send process does not block leads based on address deliverability.
Run `--check-bounces` after sending to scan recent Gmail delivery-failure
notifications and identify the affected lead IDs. Detected failures are added
to `sent_log.csv` with status `bounced`; the original `sent` record remains,
so the lead is still auditable and is not silently removed.

No mode (same as preview):

    python main.py

## Troubleshooting

### `main.py: error: one of the arguments --preview --send --auth-test is required`

This message came from an older CLI version. The current version defaults to
safe preview mode when no mode is provided. Use `python main.py --preview`
explicitly, or use `python main.py --send` only when you are ready to send.

### `ModuleNotFoundError: No module named 'google.auth'`

Activate the virtual environment and install the dependencies:

    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt

Preview does not require Gmail packages, but `--auth-test` and `--send` do.

### `ERROR: ...`

Setup and runtime errors are printed as a short `ERROR:` message and the
program exits with status 1. Check the message first. Common fixes are:

- Run commands from the folder containing `main.py`, `leads.csv`, and `messages.csv`.
- Check that both CSV files exist and contain the required columns.
- For Gmail errors, check `credentials.json`, Google Cloud Gmail API access, and `token.json`.

### "credentials.json not found"

Download the Desktop OAuth client JSON from Google Cloud and put it beside main.py.

### Google says app isn't verified

For a personal/testing desktop app, Google may show an unverified-app warning depending on how the OAuth project is configured. Only authorize your own app if you trust the project and understand the requested permission.

### OAuth changed / wrong account

Delete token.json and run again:

    python main.py --auth-test

### Email did not send

Check:
- recipient address
- Gmail account
- Google Cloud Gmail API is enabled
- OAuth consent configuration
- terminal error
- sent_log.csv

### CSV errors

Save CSV files as UTF-8 CSV. Keep the required columns:
- leads.csv: lead_id, name, email, company, website
- messages.csv: lead_id, subject, body
