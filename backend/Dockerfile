FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Warm the caches at build time so the first request on Render is fast:
# downloads the embedding model, embeds the corpus, trains the pricing model.
RUN python -c "from app.config import get_settings; from app.services import Services; Services(get_settings())"
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
