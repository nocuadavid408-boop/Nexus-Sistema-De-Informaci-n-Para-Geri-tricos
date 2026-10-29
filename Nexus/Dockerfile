FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt package.json package-lock.json ./
RUN pip install --no-cache-dir -r requirements.txt && npm ci --omit=dev
COPY . .
ENV TZ=America/Bogota
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
