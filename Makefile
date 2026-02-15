.PHONY: sync lint format test check run docker-build

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
