FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

EXPOSE 5060

# Webhook server. Gunicorn for production; swap to `python run.py` for dev.
CMD ["gunicorn", "--bind", "0.0.0.0:5060", "--workers", "2", "run:app"]
