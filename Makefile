.PHONY: help up down logs build ingest test eval adversarial lint demo clean

help:
	@echo "Targets:"
	@echo "  up           - docker compose up --build"
	@echo "  down         - docker compose down"
	@echo "  logs         - tail api logs"
	@echo "  build        - rebuild backend + frontend images"
	@echo "  ingest       - run ingest CLI inside api container"
	@echo "  test         - pytest unit + integration + adversarial"
	@echo "  eval         - run Ragas eval suite"
	@echo "  adversarial  - run adversarial prompt-injection suite"
	@echo "  lint         - import-linter + ruff"
	@echo "  demo         - up + open UI"
	@echo "  clean        - down + remove volumes"

up:
	docker compose up --build -d
	@echo "API:       http://localhost:8080"
	@echo "Frontend:  http://localhost:3000"
	@echo "Langfuse:  http://localhost:3001 (admin@mesa.local / admin1234)"

down:
	docker compose down

logs:
	docker compose logs -f api

build:
	docker compose build api frontend

ingest:
	docker compose exec api python -m scripts.ingest

test:
	docker compose exec api pytest -v

eval:
	docker compose exec api python -m eval.run_ragas

adversarial:
	docker compose exec api pytest tests/adversarial -v

lint:
	docker compose exec api lint-imports
	docker compose exec api ruff check src tests

demo: up
	@sleep 5
	xdg-open http://localhost:3000 2>/dev/null || open http://localhost:3000 2>/dev/null || true

clean:
	docker compose down -v
