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

test:          ## Run backend tests in the dev image
	docker build -q --target dev -t ai-task-bot-dev ./backend && docker run --rm ai-task-bot-dev pytest -q

lint:
	docker build -q --target dev -t ai-task-bot-dev ./backend && docker run --rm ai-task-bot-dev ruff check app tests
