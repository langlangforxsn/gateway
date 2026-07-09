FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY frontend/ ./frontend/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

EXPOSE ${PORT}

CMD exec gunicorn --bind "0.0.0.0:${PORT}" --timeout 120 --log-level debug app:app
