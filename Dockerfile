FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Verify at build time exactly where mcp-clickhouse landed -- this shows
# up in the Cloud Build logs, so if the path ever changes we see it
# immediately instead of discovering it via a runtime crash.
RUN which mcp-clickhouse

COPY main.py .

ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}