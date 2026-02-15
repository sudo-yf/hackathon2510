.PHONY: sync lint format test check run docker-build docker-run

sync:
	uv sync

lint:
	uv run ruff check app.py src tests

format:
	uv run ruff format app.py src tests

test:
	uv run pytest -q

check: lint test

run:
	uv run python app.py

docker-build:
	docker build -t waytoagi-gesture:latest .

docker-run:
	docker compose up --build
