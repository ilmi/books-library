FROM ghcr.io/astral-sh/uv:debian


WORKDIR /app

COPY . . 

RUN uv sync

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]