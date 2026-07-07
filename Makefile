.PHONY: dev lint format test docker deploy

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

deploy:
	git push origin main

precommit:
	pre-commit run --all-files
