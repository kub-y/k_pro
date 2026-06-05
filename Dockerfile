FROM python:3.14.3
RUN api-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY req.txt .
RUN pip install --no-cache-dir -r req.txt
COPY . .
EXPOSE 8000
