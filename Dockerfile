FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DOCLENS_SEARCH_ONLY=true
WORKDIR /app
COPY pyproject.toml ./
COPY doclens/ ./doclens/
COPY data/chunks.json ./data/chunks.json
RUN pip install --no-cache-dir . && useradd --uid 1000 --create-home app
USER app
EXPOSE 10000
CMD ["uvicorn", "doclens.app:app", "--host", "0.0.0.0", "--port", "10000"]
