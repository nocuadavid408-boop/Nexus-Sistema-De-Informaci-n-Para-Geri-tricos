FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=America/Bogota

# Node.js: lo usa routers/pdf.py para generar los PDF (generar_pdf.js)
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY . .

EXPOSE 8000

# --proxy-headers: detrás del proxy HTTPS de la plataforma, para que url_for() genere https://
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
