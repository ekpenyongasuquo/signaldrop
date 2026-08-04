FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# mcp-clickhouse is installed via requirements.txt, and its console
# entry point must be on PATH inside the container -- pip install
# already handles this correctly for a standard venv-free container.

COPY main.py .

# Cloud Run injects the PORT env var; the app must listen on it.
ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}