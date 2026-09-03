FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY worker.py .

EXPOSE 8000

# Default command runs the API; docker-compose overrides this to `python worker.py` for the
# consolidation-worker service, which shares this same image (see ../../docker-compose.yml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
