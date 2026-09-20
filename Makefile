.PHONY: api console worker eval test lint fmt compose-up compose-down sync

UV ?= uv
NPM ?= npm

api:
	cd backend && $(UV) run uvicorn verify.api.app:app --reload --host 0.0.0.0 --port 8000

console:
	cd console && $(NPM) run dev

worker:
	cd backend && $(UV) run python -m verify.workers.process

eval:
	cd backend && $(UV) run python -m verify.eval

test:
	cd backend && $(UV) run pytest

lint:
	cd backend && $(UV) run ruff check .

fmt:
	cd backend && $(UV) run ruff format .

sync:
	cd backend && $(UV) sync
	cd console && $(NPM) install

compose-up:
	docker compose up --build

compose-down:
	docker compose down -v
