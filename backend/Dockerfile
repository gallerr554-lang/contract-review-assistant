FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        antiword \
        fontconfig \
        libreoffice-writer \
        fonts-noto-cjk \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

RUN command -v pdftoppm \
    && command -v soffice \
    && command -v tesseract \
    && fc-match "Noto Sans CJK SC" \
    && tesseract --list-langs | grep -qx eng \
    && tesseract --list-langs | grep -qx chi_sim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY alembic ./alembic
COPY alembic.ini .
COPY docker-entrypoint.sh /usr/local/bin/contract-review-entrypoint

RUN chmod +x /usr/local/bin/contract-review-entrypoint \
    && mkdir -p /app/storage

EXPOSE 8000

ENTRYPOINT ["contract-review-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
