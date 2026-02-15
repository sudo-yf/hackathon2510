.PHONY: sync lint format test check run doctor docker-build docker-run release-bundle

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

doctor:
	uv run python app.py doctor

docker-build:
	docker build -t waytoagi-gesture:latest .

docker-run:
	docker compose up --build

release-bundle:
	python3 scripts/release_bundle.py
