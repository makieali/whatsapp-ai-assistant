"""LLM client factory for OpenAI or Azure OpenAI (lazy-imported)."""
from __future__ import annotations

from functools import lru_cache

from config import Config


@lru_cache(maxsize=1)
def get_client():
    if Config.use_azure():
        from openai import AzureOpenAI

        return AzureOpenAI(
            api_key=Config.AZURE_OPENAI_API_KEY,
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            api_version=Config.AZURE_OPENAI_API_VERSION,
        )

    from openai import OpenAI

    return OpenAI(api_key=Config.OPENAI_API_KEY)


def create_chat(messages, **overrides):
    """Call chat.completions, adaptively dropping params a model rejects.

    Some deployments (e.g. fixed-temperature GPT-5 models) reject ``temperature``
    or other params; we retry without any single param the API reports as
    unsupported so the app works across model variants.
    """
    client = get_client()
    params = {"model": Config.chat_model(), "messages": messages, "temperature": 0.5}
    params.update(overrides)
    for _ in range(len(params)):
        try:
            return client.chat.completions.create(**params)
        except Exception as exc:  # noqa: BLE001
            dropped = _unsupported_param(exc, params)
            if dropped is None:
                raise
            params.pop(dropped, None)
    return client.chat.completions.create(**params)


def _unsupported_param(exc: Exception, params: dict) -> str | None:
    msg = str(getattr(exc, "message", "") or exc).lower()
    if "unsupported" not in msg and "not supported" not in msg:
        return None
    for name in ("temperature", "response_format", "max_tokens"):
        if name in params and name in msg:
            return name
    return None
