FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CAREVOICE_DATA_DIR=/var/data

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        espeak-ng \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        nginx \
        portaudio19-dev \
        supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/supervisord.conf /etc/supervisor/conf.d/carevoice.conf

RUN mkdir -p /var/data

EXPOSE 10000

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
