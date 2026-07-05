.PHONY: dev lint format test docker

dev:
	uvicorn app.main:app --reload --port 8000

lint:
	ruff check .

format:
	ruff format .

test:
	python -m pytest -v

docker:
	docker compose up --build

precommit:
	pre-commit run --all-files
