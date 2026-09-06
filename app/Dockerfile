FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app/main.py /app/main.py
COPY models/model.joblib /app/models/model.joblib

RUN useradd -m -u 10001 appuser && chown -R appuser /app
USER appuser

ENV MODEL_PATH=/app/models/model.joblib PORT=8080
EXPOSE 8080
CMD ["sh","-c","uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 2 --backlog 4096 --timeout-keep-alive 5"]
