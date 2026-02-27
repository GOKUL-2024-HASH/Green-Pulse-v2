FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.pipeline.txt .
RUN pip install --no-cache-dir -r requirements.pipeline.txt

COPY pipeline/ ./pipeline/
COPY config/ ./config/

CMD ["python", "-m", "pipeline.main"]
