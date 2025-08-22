# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# tzdata lets us set Europe/Athens so tickler times match your local habit
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/*

# App directory
WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy app
COPY gtd_bot.py .

# Create non-root user
RUN useradd -u 10001 -m appuser
USER appuser

# Set timezone for cron-like timers inside the app
ENV TZ=Europe/Athens

# Default command
CMD ["python", "/app/gtd_bot.py"]

