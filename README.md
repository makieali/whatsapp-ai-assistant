<div align="center">

# 💬 WhatsApp AI Assistant

### A multimodal AI assistant for WhatsApp — understands **text, photos, and voice notes**.

Point a WhatsApp Business number at this webhook and users can chat with an AI, send a photo to get it described or analyzed, or send a voice note to have it transcribed and answered — all with conversation memory.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-37%20passing-brightgreen.svg)](#-testing)
[![Coverage](https://img.shields.io/badge/coverage-81%25-brightgreen.svg)](#-testing)
[![Providers](https://img.shields.io/badge/LLM-OpenAI%20%7C%20Azure-412991.svg)](#-configuration)

</div>

---

## Why this exists

This began as a WhatsApp ↔ GPT-3.5 text bot that, despite its name, had **no vision** and read voice notes through a fragile Google-SpeechRecognition + `pydub` + `soundfile` + OGG→WAV pipeline. It also shipped with **API keys hardcoded in source**.

This rebuild fixes all of that and delivers the multimodal assistant the name always implied:

| | **Before** | **After** (this repo) |
|---|---|---|
| Images | ❌ none | ✅ **vision** — send a photo, get an answer |
| Voice notes | Google SR + pydub + soundfile | ✅ one **Whisper** call |
| Model | `gpt-3.5-turbo` | `gpt-4o-mini` (vision) — OpenAI **or** Azure |
| Secrets | **hardcoded in `app.py`** | environment variables only |
| Webhook security | verify-token only | + **HMAC `X-Hub-Signature-256`** validation |
| Memory | unbounded dict (grows forever) | bounded per-user history |
| Structure | one 250-line file | small, testable modules |
| Tests | none | 37 tests, ~81% coverage |

## ✨ Features

- 💬 **Text chat** with per-user conversation memory (bounded so it never grows unbounded).
- 🖼️ **Vision** — send a photo (with an optional caption) and the assistant analyzes it.
- 🎙️ **Voice notes** — transcribed with Whisper, then answered.
- 🔐 **Signed webhooks** — validates Meta's `X-Hub-Signature-256` so spoofed requests are rejected.
- 🧭 **Commands** — `/help` and `/reset` handled without an AI call.
- 🔌 **OpenAI or Azure OpenAI**, with adaptive params (drops anything a model rejects and retries).
- 🩺 **Robust webhook** — always returns `200` for non-message events and handler errors so Meta doesn't spam retries; `/healthz` for uptime checks.

## 🏗️ How it works

```
WhatsApp user
     │  text / photo / voice
     ▼
Meta Cloud API ──POST /webhook──►  verify signature ─► parse_webhook ─► IncomingMessage
                                                                              │
                              ┌───────────────────────────────────────────────┤
                              ▼                      ▼                         ▼
                         text → chat          image → vision           audio → Whisper → chat
                              └──────────── ConversationMemory ─────────────────┘
                                                     │
                                          reply ──► WhatsApp Cloud API ──► user
```

Each layer is its own module: [`app/whatsapp/`](app/whatsapp) (parse / verify / send), [`app/ai/`](app/ai) (chat / vision / transcribe), [`app/memory.py`](app/memory.py), and [`app/handler.py`](app/handler.py) ties them together — independent of Flask and unit-tested in isolation.

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

> **Voice notes** require a Whisper-capable endpoint. Standard OpenAI has `whisper-1`; on Azure you need a separate Whisper deployment, otherwise voice falls back to a friendly error while text and vision keep working.

## 🧪 Testing

```bash
pip install -r requirements.txt
pytest                     # 37 passed, ~81% coverage
```

Tests mock the model and the WhatsApp HTTP calls, so the suite runs **offline with no keys**. They cover payload parsing, signature verification, bounded memory, the outbound client (mocked HTTP), message dispatch for all three modalities, and the full webhook route (including signature rejection and "never 500 the webhook" behavior).

> Verified end-to-end against a live Azure OpenAI vision deployment: a text question, a **memory-dependent follow-up**, and an **image with a caption** were all answered correctly through the real handler pipeline (WhatsApp transport mocked).

## 🔒 Security notes

- **No secrets in the repo.** Everything sensitive comes from `.env`, which is git-ignored.
- **Verify signatures in production.** Set `WHATSAPP_APP_SECRET` so forged webhook calls are rejected. Without it, signature checking is skipped for local dev.
- Conversation memory is **in-process** ([`app/memory.py`](app/memory.py)); for multi-worker or persistent deployments, back it with Redis — the interface is tiny.

## 📁 Project layout

```
whatsapp-ai-assistant/
├── run.py                  # entrypoint
├── config.py              # env config (OpenAI + Azure + WhatsApp)
├── app/
│   ├── __init__.py        # app factory
│   ├── routes.py          # /, /healthz, /webhook (verify + receive)
│   ├── handler.py         # dispatch: message -> reply -> send
│   ├── memory.py          # bounded per-user conversation history
│   ├── ai/                # chat · vision · transcribe · client
│   ├── whatsapp/          # parser · verify (HMAC) · client (Graph API)
│   └── templates/index.html
└── tests/                 # pytest, AI + HTTP mocked
```

## 📄 License

[MIT](./LICENSE) © 2026 Muhammad Ali
