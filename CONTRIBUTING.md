# Contributing

Thanks for your interest in improving the WhatsApp AI Assistant! 🎉

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your keys
pytest                        # everything should pass
```

The test suite mocks the model and all WhatsApp HTTP calls, so it runs offline
with no API keys.

## Project conventions

- **Small, focused modules.** AI logic lives in `app/ai/`, WhatsApp I/O in
  `app/whatsapp/`, persistence in `app/db/`. Keep `app/handler.py` and
  `app/routes.py` thin.
- **No secrets in code.** Everything sensitive comes from the environment.
- **Type hints** on function signatures; format with `black`, lint with `ruff`.
- **Tests for new behavior.** Match the existing style in `tests/`.

## Database changes

The schema is defined by the ORM models in `app/db/models.py` and versioned with
Alembic. After changing a model, generate a migration:

```bash
# Point DATABASE_URL at a scratch DB, then:
alembic revision --autogenerate -m "describe your change"
alembic upgrade head           # verify it applies
```

Commit the generated file in `migrations/versions/`.

## Running the Postgres test path locally

```bash
createdb whatsbot_test
TEST_DATABASE_URL=postgresql://localhost/whatsbot_test pytest
```

(CI runs this automatically against a Postgres service.)

## Pull requests

1. Branch off `main`.
2. Keep the diff focused; one logical change per PR.
3. Make sure `pytest` passes and add tests for new behavior.
4. Describe what changed and why.
