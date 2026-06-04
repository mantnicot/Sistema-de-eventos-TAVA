FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app/src

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads \
    && chmod +x docker-entrypoint.sh

ENV PYTHONPATH=/app/src

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
