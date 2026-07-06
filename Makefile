.PHONY: dev lint format test docker push

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

push:
	git push origin main
	git push origin --tags

precommit:
	pre-commit run --all-files
