# Local Gmail Unread Digest — Phase 1

A local, read-only Gmail assistant that retrieves messages matching
`in:inbox is:unread` and produces a deterministic digest without sending Gmail
content to an external AI service.

This project is designed for privacy-sensitive mailboxes, including USC email,
but software design alone does not establish legal or institutional approval.
Confirm any role-, department-, research-, device-, or account-specific
requirements with the appropriate USC office before using it with protected data.

## Privacy and security warning

> **Do not commit credentials.json, token.json, .env,**
> **API keys, OAuth tokens, or exported email data.**

Do not paste live USC email content, application output, OAuth errors containing
tokens, or credentials into ChatGPT or another external AI tool. Run live mailbox
operations only in a trusted local terminal.

### Phase 1 privacy boundary

- Gmail retrieval and analysis happen in the local Python process.
- The only OAuth scope is
  `https://www.googleapis.com/auth/gmail.readonly`.
- Raw bodies are held temporarily in memory while each message is analyzed.
- Full raw messages and bodies are not stored in a database or cache.
- The in-memory sync cache contains derived `EmailSummary` objects only.
- The application does not separately fetch Gmail attachments. Gmail may include
  small inline MIME-part data in a message response. Attachment-part data is
  discarded locally before parsing or analysis and is not logged, persisted,
  summarized, or transmitted to another service.
- Inline `text/plain` is preferred; HTML is locally converted to text after
  scripts, styles, images, and other active/tracking elements are removed.
- Logs contain counts and one-way, truncated message-ID hashes. They do not
  intentionally contain senders, subjects, bodies, or OAuth values.
- API responses contain selected metadata and derived summaries, never a raw
  body or MIME payload field.
- HTTP responses use `Cache-Control: no-store`.
- No OpenAI library, external AI provider, telemetry SDK, or analytics service is
  included.

The `EmailSummarizer` interface isolates analysis. Phase 1 provides only
`LocalSummarizer`. A future USC-approved enterprise implementation can replace it
after a formal privacy and policy review; there is deliberately no raw-email
OpenAI implementation.

## What Phase 1 does

- Uses the official Gmail API and installed-application OAuth 2.0 flow.
- Retrieves unread inbox messages without changing Gmail state.
- Parses nested MIME messages and base64url-encoded inline text.
- Removes likely quoted history and long signatures where practical.
- Produces a concise extractive summary and explainable heuristic assessments.
- Distinguishes required, recommended, optional, absent, and uncertain action.
- Classifies explicit dates as deadlines, events, historical, publication,
  promotional, referenced, or unknown without treating every date as urgent.
- Resolves relative date phrases against the message receipt time converted to
  the configured local IANA timezone (America/Los_Angeles by default).
- Represents event presence, attendance requirements, and registration
  availability, requirements, completion, and deadlines separately from general
  action.
- Distinguishes upcoming, ongoing, past, and uncertain event status relative to
  the message's received date.
- Conservatively groups near-identical unread messages while retaining the
  original unread count and showing the number of similar messages.
- Groups results into urgent, action, reply, informational, promotional, and
  manual-review sections with counts.
- Offers FastAPI endpoints and a terminal digest command.

## Deliberately not implemented

Phase 1 does **not** send or reply to email, mark messages read, modify labels,
archive or delete mail, separately fetch or analyze attachments, monitor in the background, create
calendar events, deploy a service, persist mailbox bodies, or submit Gmail data
to external AI.

Heuristic results are aids for review, not authoritative determinations. The app
can miss important language or assign the wrong category. It never treats a
date without enough context as a confirmed deadline.

Promotional wording is not sufficient for urgency or required action. Sender
domains, including institutional domains, do not determine importance by
themselves. Ambiguous academic or administrative messages remain available for
manual review instead of being automatically hidden as low priority.

Message format and user value are separate. A newsletter may remain a newsletter
while being routed to `UPCOMING EVENTS`, and a bulk or promotional message with a
credible academic, administrative, security, or required-registration deadline
can route to `NEEDS ACTION`. Optional registration for an upcoming event remains
optional and stays under `UPCOMING EVENTS`; confirmed or explicitly unnecessary
registration does not create another action. Past events alone do not keep a
promotional newsletter out of low priority.

Consistency checks prevent required actions, applicable future deadlines, and
upcoming events from becoming low priority. Required registration for an upcoming
event routes to `NEEDS ACTION` unless registration is already complete.

Digest/container messages are classified as containers. Phase 1 deliberately
does not interpret dates, events, registration language, or calls to action inside
their embedded child-message summaries as direct properties of the container.

Digest sections are ordered as follows:

1. `URGENT / TIME-SENSITIVE`
2. `NEEDS ACTION`
3. `NEEDS REPLY`
4. `UPCOMING EVENTS`
5. `IMPORTANT INFORMATIONAL`
6. `OTHER INFORMATIONAL / NEWSLETTERS`
7. `LOW PRIORITY / PROMOTIONAL`
8. `REVIEW MANUALLY`

## USC policy considerations

USC's policies and guidance can change. Review the current official sources:

- [Generative AI General Policy](https://policy.usc.edu/generative-ai-general-policy/)
- [Data Protection Policy](https://policy.usc.edu/data-protection/)
- [Data Privacy Policy](https://policy.usc.edu/data-privacy-policy/)
- [Student Records Policy](https://policy.usc.edu/student-records/)
- [FERPA guidance for faculty and staff](https://arr.usc.edu/ferpa-for-faculty-and-staff/)
- [Acceptable Use Policy](https://policy.usc.edu/acceptable-use/)

USC identifies internal emails and USC IDs as Internal Use Only examples, and
student records, health data, and nonpublic financial data may be Confidential or
more restricted. USC guidance warns that uploading student information to a
generative AI platform may violate FERPA. This is why Phase 1 has no external AI
path at all.

If USC administrators block the OAuth client, or if your account/device rules do
not permit this use, do not work around those controls. Contact USC ITS,
Cybersecurity, the Office of Ethics and Compliance, or the relevant data owner.

## Requirements

- Python 3.12 or newer
- A trusted local computer with full-disk encryption and a protected OS account
- A Google Cloud project allowed to access the intended Gmail account
- Gmail API enabled for that project
- An OAuth 2.0 Desktop app credential

This repository does not bundle Python. Confirm the runtime first:

```powershell
python --version
```

## Google Cloud, Gmail API, and OAuth setup

Google's current [Python Gmail quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python)
is the authoritative reference. Console labels can change.

1. Sign in to Google Cloud using an account authorized to create the project.
2. Create or select a dedicated project for this local application.
3. In **APIs & Services → Library**, find and enable **Gmail API**.
4. In **Google Auth Platform**, configure Branding and Audience.
   - Choose **Internal** only if the project belongs to the applicable Google
     Workspace organization and USC permits this configuration.
   - Otherwise use **External / Testing** and add only the intended account as a
     test user. Do not publish the app merely to bypass access controls.
5. Under **Data Access**, configure only:

   ```text
   https://www.googleapis.com/auth/gmail.readonly
   ```

6. Under **Clients**, create an OAuth client with application type **Desktop app**.
7. Download the client JSON, rename it `credentials.json`, and place it in the
   repository root beside this README.
8. Verify Git ignores it before doing anything else:

   ```powershell
   git check-ignore -v credentials.json
   ```

Google Workspace administrators can restrict third-party or internal OAuth apps.
Authorization failure may therefore require administrator review—not broader
scopes or a workaround.

## Local installation

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` contains paths and behavior settings, not Google client secrets. It is
still ignored because local configuration can reveal sensitive operational
details.

Available settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `GMAIL_ASSISTANT_CREDENTIALS_PATH` | `credentials.json` | Local OAuth client file |
| `GMAIL_ASSISTANT_TOKEN_PATH` | `token.json` | Local OAuth token file |
| `GMAIL_ASSISTANT_QUERY` | `in:inbox is:unread` | Gmail search query; the legacy `GMAIL_ASSISTANT_UNREAD_QUERY` name is also accepted |
| `GMAIL_ASSISTANT_MAX_MESSAGES` | `100` | Per-run cap, from 1 through 500 |
| `GMAIL_ASSISTANT_DEFAULT_TIMEZONE` | `America/Los_Angeles` | IANA timezone used to resolve relative date language |
| `GMAIL_ASSISTANT_LOG_LEVEL` | `INFO` | Operational log level |

Do not change the query to retrieve data you are not authorized to process.

## Authenticate and generate a digest

The first Gmail-dependent command opens Google's local OAuth consent flow:

```powershell
python -m app.cli digest
```

Confirm that the consent screen requests read-only Gmail access. After approval,
Google credentials are stored locally in `token.json`. That file can contain a
refresh token: protect the device, restrict access to your OS account, and never
copy the file into email, chat, cloud-sync folders, tickets, or repositories.
Google's [OAuth security guidance](https://developers.google.com/identity/protocols/oauth2/resources/best-practices)
recommends secure platform storage for user tokens; local JSON storage here is a
Phase 1 compatibility choice and should be revisited before broader use.

The local OAuth callback can contain a short-lived authorization code and state
value. The application suppresses the OAuth library's callback-request INFO log,
does not print the authorization URL when the browser opens automatically, and
defensively redacts OAuth query parameters from application log handlers.

For JSON output:

```powershell
python -m app.cli digest --json
```

The output itself can contain sensitive derived information. Do not redirect it
to a tracked file or share it with an external AI service.

## Run the local API

Bind only to the loopback interface:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /health` — local status and declared security posture; no Gmail call
- `GET /unread` — fresh derived summaries, without raw bodies
- `GET /digest/unread` — fresh grouped digest and counts
- `POST /sync` — refreshes the in-memory derived-summary cache only

Example local request:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/digest/unread
```

Do not use `--host 0.0.0.0`, expose the port through a firewall or tunnel, or put
this development API behind a public proxy. Phase 1 has no user-authentication
layer because it is intentionally localhost-only.

## Run tests

Tests are offline, use synthetic content, and mock Gmail calls. They require no
Google account, Gmail credentials, OpenAI key, or internet connection.

```powershell
python -m pytest -q
```

Coverage areas include MIME parsing, HTML sanitization, nested multiparts,
attachment exclusion, quoted-thread trimming, encoded headers, date confidence,
priority/action/reply heuristics, digest grouping, read-only Gmail operations,
privacy-safe logging, non-caching API responses, and Git ignore rules.

## Verify no secrets or personal data are tracked

Before every commit, run:

```powershell
git status --short
git diff --cached --name-only
git ls-files
git grep -n -I -E "(access[_-]?token|refresh[_-]?token|client[_-]?secret|api[_-]?key|Authorization: Bearer)"
git check-ignore -v credentials.json token.json .env
```

Inspect all staged diffs, not just filenames:

```powershell
git diff --cached
```

Expected: `credentials.json`, `token.json`, and `.env` are ignored and absent
from both `git ls-files` and staged output. Also manually check for exported
messages, names, account identifiers, student IDs, grades, financial or health
information, research data, and other personal or USC data. Automated pattern
checks cannot prove a repository is clean.

If a secret was ever committed, removing the current file is insufficient.
Revoke/rotate the credential and treat Git history as exposed.

## Architecture and future extension

```text
READ-ONLY GMAIL
      ↓
UNREAD MIME PAYLOADS (attachment-part data discarded immediately)
      ↓
LOCAL PARSER → LocalSummarizer
      ↓
DERIVED EmailSummary OBJECTS
      ↓
LOCAL CLI / LOCALHOST API DIGEST
```

Future phases may add calendar suggestions, appointments, reply tracking,
scheduled digests, archiving, and an institution-approved AI summarizer. None is
implemented or authorized by this Phase 1 code. Any new data flow requires a new
privacy, security, OAuth-scope, and USC-policy review first.
