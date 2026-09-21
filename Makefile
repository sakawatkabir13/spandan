.PHONY: help up down restart logs test test-frontend check migrate seed clean

help:
	@echo "Spandan Management Commands:"
	@echo "  make up         - Start all services (db, backend, frontend) via Docker Compose"
	@echo "  make down       - Stop all services and remove containers"
	@echo "  make restart    - Restart all services"
	@echo "  make logs       - Follow logs of all services"
	@echo "  make migrate    - Run Alembic database migrations inside backend container"
	@echo "  make seed       - Run seed script inside backend container"
	@echo "  make test       - Run backend tests via Pytest inside backend container"
	@echo "  make clean      - Remove volumes, containers, and temporary files"

up:
	docker compose up --build -d

down:
	docker compose down

restart:
	docker compose down && docker compose up --build -d

logs:
	docker compose logs -f

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python -m scripts.seed

test:
	docker compose exec backend pytest -v

clean:
	docker compose down -v
	rm -rf backend/.pytest_cache backend/htmlcov backend/.coverage

test-frontend:
	docker compose exec frontend npm test

check:
	docker compose exec backend ruff check .
	docker compose exec backend pytest -q
	docker compose exec frontend npm test
	docker compose exec frontend npm run build
