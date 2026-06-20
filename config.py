"""Configuration loaded from environment variables.

No secrets are hardcoded -- everything comes from the environment / .env file.
Supports standard OpenAI or Azure OpenAI for the AI layer.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str) -> bool:
    return str(value).lower() in ("true", "1", "t", "yes")


class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = _as_bool(os.getenv("FLASK_DEBUG", "false"))
    PORT = int(os.getenv("PORT", "5060"))

    # LLM provider -- standard OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    MODEL = os.getenv("MODEL", "gpt-4o-mini")
    TRANSCRIBE_MODEL = os.getenv("TRANSCRIBE_MODEL", "whisper-1")

    # LLM provider -- Azure OpenAI (priority if key present)
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    # WhatsApp Cloud API
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
    WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")
    GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")

    # Assistant behaviour
    SYSTEM_PROMPT = os.getenv(
        "SYSTEM_PROMPT",
        "You are WhatsBot, a helpful, concise WhatsApp assistant. Keep replies "
        "short and friendly, suitable for a chat message. Use the user's language.",
    )
    MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "12"))

    # Conversation store. Unset -> in-process memory (single worker / tests).
    # Set -> shared, persistent SQL store, e.g.
    #   sqlite:///conversations.db   or   postgresql://user:pass@host/db
    DATABASE_URL = os.getenv("DATABASE_URL")

    @classmethod
    def use_azure(cls) -> bool:
        return bool(cls.AZURE_OPENAI_API_KEY)

    @classmethod
    def chat_model(cls) -> str:
        return cls.AZURE_OPENAI_DEPLOYMENT if cls.use_azure() else cls.MODEL

    @classmethod
    def require_ai(cls) -> None:
        if cls.use_azure():
            if not (cls.AZURE_OPENAI_ENDPOINT and cls.AZURE_OPENAI_DEPLOYMENT):
                raise RuntimeError("Azure OpenAI needs AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT")
            return
        if not cls.OPENAI_API_KEY or cls.OPENAI_API_KEY.startswith("sk-your"):
            raise RuntimeError("Set OPENAI_API_KEY (or the AZURE_OPENAI_* block) in .env")

    @classmethod
    def require_whatsapp(cls) -> None:
        missing = [n for n, v in (
            ("WHATSAPP_TOKEN", cls.WHATSAPP_TOKEN),
            ("WHATSAPP_PHONE_NUMBER_ID", cls.WHATSAPP_PHONE_NUMBER_ID),
        ) if not v]
        if missing:
            raise RuntimeError(f"WhatsApp config missing: {', '.join(missing)}")
