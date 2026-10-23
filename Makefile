.PHONY: up down build logs ps test lint

up:            ## Build and start the whole stack
	docker compose up --build -d

down:          ## Stop and remove containers (keeps the database volume)
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

test:          ## Backend tests against real Postgres + Redis (test db/index, never touches app data)
	docker compose --profile test run --build --rm test pytest -q

lint:
	docker compose --profile test run --build --rm --no-deps test ruff check app tests

web-test:      ## Frontend unit tests + typecheck (needs node locally)
	cd frontend && npm test && npm run typecheck
