# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies required for Playwright browsers and build tooling
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        tesseract-ocr \
        libtesseract-dev \
        libjpeg-dev \
        zlib1g-dev \
        libpng-dev \
        ffmpeg \
        libavcodec-extra \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ /tmp/requirements/

RUN pip install --upgrade pip setuptools wheel \
    && pip install -r /tmp/requirements/production.requirements.txt \
    && playwright install --with-deps chromium

COPY . /app

ENV PYTHONPATH=/app

CMD ["sleep", "infinity"]
