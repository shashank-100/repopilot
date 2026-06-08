.PHONY: up down dev dev-ui test lint fmt eval install db-migrate

install:
	uv sync

up:
	docker compose up -d

down:
	docker compose down

dev:
	uv run uvicorn repopilot.api.main:app --reload --host 0.0.0.0 --port 8000

dev-ui:
	cd dashboard && npm run dev

test:
	uv run python -m pytest tests/ -x --cov=repopilot --cov-report=term-missing

lint:
	uv run ruff check repopilot/ tests/
	uv run mypy repopilot/

fmt:
	uv run ruff format repopilot/ tests/
	uv run ruff check --fix repopilot/ tests/

eval:
	uv run python -m repopilot.evaluation.run --repo $(REPO)

db-migrate:
	uv run alembic upgrade head
