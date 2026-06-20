<div align="center">

# 💬 WhatsApp AI Assistant

### A multimodal AI assistant for WhatsApp — understands **text, photos, and voice notes**.

Point a WhatsApp Business number at this webhook and users can chat with an AI, send a photo to get it described or analyzed, or send a voice note to have it transcribed and answered — all with conversation memory.

[![CI](https://github.com/makieali/whatsapp-ai-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/makieali/whatsapp-ai-assistant/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-55%20passing-brightgreen.svg)](#-testing)
[![DB](https://img.shields.io/badge/DB-PostgreSQL%20%7C%20SQLite-336791.svg)](#-conversation-memory--database)
[![Providers](https://img.shields.io/badge/LLM-OpenAI%20%7C%20Azure-412991.svg)](#-configuration)

</div>

---

## Why this exists

This began as a WhatsApp ↔ GPT-3.5 text bot that, despite its name, had **no vision** and read voice notes through a fragile Google-SpeechRecognition + `pydub` + `soundfile` + OGG→WAV pipeline. It also shipped with **API keys hardcoded in source**.

This rebuild delivers the multimodal assistant the name always implied: it adds
**vision** (send a photo, get an answer), swaps the fragile speech stack for a
single **Whisper** call, runs on a modern model via **OpenAI or Azure**, moves
every secret into the environment, verifies webhook signatures, bounds and
persists conversation memory, and splits the old single file into small, tested
modules.

## ✨ Features

- 💬 **Text chat** with per-user conversation memory — bounded, and optionally **persisted to SQLite/Postgres** so it's shared across workers and survives restarts.
- 🖼️ **Vision** — send a photo (with an optional caption) and the assistant analyzes it.
- 🎙️ **Voice notes** — transcribed with Whisper, then answered.
- 🔐 **Signed webhooks** — validates Meta's `X-Hub-Signature-256` so spoofed requests are rejected.
- 🧭 **Commands** — `/help` and `/reset` handled without an AI call.
- 🔌 **OpenAI or Azure OpenAI**, with adaptive params (drops anything a model rejects and retries).
- 🗄️ **Relational persistence** — optional Postgres/SQLite store with a `users → conversations → messages` schema, shared across workers and durable across restarts.
- ♻️ **Idempotent ingestion** — a unique `wa_message_id` means WhatsApp's re-delivered webhooks are never processed (or answered) twice.
- 🩺 **Robust webhook** — always returns `200` for non-message events and handler errors so Meta doesn't spam retries; `/healthz` and `/stats` for monitoring.

## 🏗️ How it works

<!-- Rendered by GitHub's built-in Mermaid support -->
```mermaid
flowchart TD
    U(["📱 WhatsApp user"]) -->|"text · photo · voice"| META["Meta Cloud API"]
    META -->|"POST /webhook"| V{"verify signature<br/>(HMAC)"}
    V -->|valid| P["parse_webhook → IncomingMessage"]
    P --> R{"route by type"}
    R -->|text| C["💬 chat"]
    R -->|image| VIS["🖼️ vision"]
    R -->|audio| W["🎙️ Whisper → chat"]
    C --> MEM[("conversation store<br/>users · conversations · messages")]
    VIS --> MEM
    W --> MEM
    MEM --> REPLY["reply"]
    REPLY -->|"WhatsApp Cloud API"| U
```

Each layer is its own module: [`app/whatsapp/`](app/whatsapp) (parse / verify / send), [`app/ai/`](app/ai) (chat / vision / transcribe), [`app/db/`](app/db) + [`app/memory.py`](app/memory.py) (persistence), and [`app/handler.py`](app/handler.py) ties them together — independent of Flask and unit-tested in isolation.

## 🚀 Quickstart

```bash
git clone https://github.com/makieali/whatsapp-ai-assistant.git
cd whatsapp-ai-assistant

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env       # fill in your keys (see below)
python run.py              # → http://localhost:5060
```

To receive real messages you need to expose the webhook publicly (e.g. `ngrok http 5060`) and register it with Meta — see the setup guide below.

## 📲 Connecting WhatsApp (one-time setup)

1. Create a Meta app at [developers.facebook.com](https://developers.facebook.com/) and add the **WhatsApp** product.
2. From **WhatsApp → API Setup**, copy your **temporary access token** and **Phone number ID** into `.env` (`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`).
3. From **App → Settings → Basic**, copy the **App Secret** into `WHATSAPP_APP_SECRET` (enables signature verification).
4. Expose your server: `ngrok http 5060`.
5. In **WhatsApp → Configuration → Webhook**, set the callback URL to `https://<your-ngrok>/webhook`, set the **Verify Token** to the same value as `WHATSAPP_VERIFY_TOKEN`, and **Subscribe** to the `messages` field.
6. Message your test number from WhatsApp. 🎉

## ⚙️ Configuration

All via environment variables (see [`.env.example`](./.env.example)):

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` / `MODEL` | Standard OpenAI key + vision model (default `gpt-4o-mini`). |
| `AZURE_OPENAI_*` | Use Azure instead (takes priority if the key is set). |
| `TRANSCRIBE_MODEL` | Whisper model for voice notes (default `whisper-1`). |
| `WHATSAPP_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` | From Meta API Setup. |
| `WHATSAPP_VERIFY_TOKEN` | You choose it; must match the Meta webhook config. |
| `WHATSAPP_APP_SECRET` | Enables `X-Hub-Signature-256` verification. |
| `MAX_HISTORY_TURNS` | Conversation turns kept per user (default 12). |
| `DATABASE_URL` | Optional. Persist + share conversation history (`sqlite:///…` or `postgresql://…`). Unset = in-process. |

> **Voice notes** require a Whisper-capable endpoint. Standard OpenAI has `whisper-1`; on Azure you need a separate Whisper deployment, otherwise voice falls back to a friendly error while text and vision keep working.

## 🧪 Testing

```bash
pip install -r requirements.txt
pytest                     # 53 passed offline; 55 with a Postgres DB
```

Tests mock the model and the WhatsApp HTTP calls, so the suite runs **offline with no keys**. They cover payload parsing, signature verification, bounded memory, the SQL repository (schema, conversation lifecycle, dedup, stats), the outbound client (mocked HTTP), message dispatch for all three modalities, and the full webhook route (including signature rejection and "never 500 the webhook" behavior).

**CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the suite on every push/PR against a real **PostgreSQL** service — applying the Alembic migration and running the Postgres-path tests (set `TEST_DATABASE_URL` to run them locally too).

> Verified end-to-end against a live Azure OpenAI vision deployment: a text question, a **memory-dependent follow-up**, and an **image with a caption** were all answered correctly through the real handler pipeline (WhatsApp transport mocked).

## 🔒 Security notes

- **No secrets in the repo.** Everything sensitive comes from `.env`, which is git-ignored.
- **Verify signatures in production.** Set `WHATSAPP_APP_SECRET` so forged webhook calls are rejected. Without it, signature checking is skipped for local dev.
- For multi-worker or persistent deployments, set `DATABASE_URL` so conversation history is shared and durable — see [Conversation memory](#-conversation-memory) below.

## 🧠 Conversation memory & database

Each user gets their own history so the assistant remembers context across
messages, bounded to the last `MAX_HISTORY_TURNS` exchanges (the system prompt is
always preserved) to keep token usage in check.

Two interchangeable stores sit behind one interface:

| Store | When | Notes |
|---|---|---|
| **In-process** ([`app/memory.py`](app/memory.py)) | `DATABASE_URL` unset | Zero setup. Tests and single-process runs. |
| **SQL repository** ([`app/db/`](app/db)) | `DATABASE_URL` set | Shared across workers, **persistent**, full relational schema. PostgreSQL (recommended) or SQLite. |

```bash
# Production — shared Postgres (recommended):
DATABASE_URL=postgresql://user:pass@localhost:5432/whatsbot
# Local file DB — nothing to install:
DATABASE_URL=sqlite:///conversations.db
```

**Why it matters:** in production the server runs multiple Gunicorn workers and
Meta load-balances a user's messages across them. With in-process memory a
follow-up can hit a worker that never saw the earlier messages — so the bot
"forgets" mid-conversation. A shared database gives every worker one view of the
history, and it survives restarts. `docker compose up` starts a ready Postgres
service and points the app at it.

### Schema

Defined by the ORM models in [`app/db/models.py`](app/db/models.py):

<!-- Rendered by GitHub's built-in Mermaid support -->
```mermaid
erDiagram
    users ||--o{ conversations : has
    conversations ||--o{ messages : contains
    users ||--o{ messages : authors

    users {
        int id PK
        string wa_id UK "phone number"
        string profile_name
        bool is_blocked
        int message_count
        datetime created_at
        datetime last_seen_at
    }
    conversations {
        int id PK
        int user_id FK
        bool is_active
        datetime started_at
        datetime ended_at
    }
    messages {
        int id PK
        int conversation_id FK
        int user_id FK
        string role "user / assistant / system"
        string message_type "text / image / audio"
        text content
        string wa_message_id UK "idempotency"
        string media_id
        datetime created_at
    }
```

- **users** — one row per WhatsApp contact, with profile name, last-seen, and message count.
- **conversations** — sessions. `/reset` closes the active one; the next message opens a fresh one, so history stays segmented (and the old transcript is preserved).
- **messages** — every turn, tagged by modality (`text` / `image` / `audio`). `wa_message_id` is **unique**, which makes ingestion **idempotent**: WhatsApp re-delivers webhooks, and the constraint stops the same message being stored or answered twice.

### `GET /stats`

When a database is configured, returns aggregate usage (counts only, no PII):

```json
{ "users": 12, "conversations": 30, "active_conversations": 11,
  "messages": 214, "messages_by_type": { "text": 180, "image": 22, "audio": 12 } }
```

### Migrations (Alembic)

The schema is versioned with [Alembic](https://alembic.sqlalchemy.org/). For a
quick local start the app auto-creates tables (`AUTO_CREATE_TABLES=true`, the
default) — nothing to run. In production, manage the schema with migrations
instead:

```bash
export DATABASE_URL=postgresql://user:pass@host:5432/whatsbot
export AUTO_CREATE_TABLES=false      # let migrations own the schema
alembic upgrade head                 # create / update tables
```

After changing a model in `app/db/models.py`, generate a migration with
`alembic revision --autogenerate -m "…"` and commit it. The Docker image runs
`alembic upgrade head` on startup automatically whenever `DATABASE_URL` is set
(see `entrypoint.sh`), so `docker compose up` provisions the schema for you.

## 📁 Project layout

```
whatsapp-ai-assistant/
├── run.py                  # entrypoint
├── config.py              # env config (OpenAI + Azure + WhatsApp)
├── app/
│   ├── __init__.py        # app factory
│   ├── routes.py          # /, /healthz, /webhook (verify + receive)
│   ├── handler.py         # dispatch: message -> reply -> send
│   ├── memory.py          # in-process store + build_memory() factory
│   ├── db/                # ORM models (users/conversations/messages) + repository
│   ├── ai/                # chat · vision · transcribe · client
│   ├── whatsapp/          # parser · verify (HMAC) · client (Graph API)
│   └── templates/index.html
├── migrations/            # Alembic migrations (versioned schema)
├── tests/                 # pytest, AI + HTTP mocked
├── .github/workflows/     # CI (pytest + Postgres service)
├── entrypoint.sh          # runs migrations then serves
└── Dockerfile · docker-compose.yml
```

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](./CONTRIBUTING.md) for setup,
conventions, and how to add a database migration. In short: branch off `main`,
keep `pytest` green, and add tests for new behavior.

## 📄 License

[MIT](./LICENSE) © 2026 Muhammad Ali
