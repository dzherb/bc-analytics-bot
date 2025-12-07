.PHONY lint:
lint:
	@uv run ruff check .

.PHONY fmt:
fmt:
	@uv run ruff check --fix .
	@uv run ruff format .

.PHONY typecheck:
typecheck:
	@uv run mypy .

.PHONY: lint-dotenv
lint-dotenv:
	@uv run dotenv-linter .env .env.template

.PHONY fullcheck:
fullcheck: lint lint-dotenv typecheck

.PHONY run-bot:
run-bot:
	@uv run -m entrypoints.telegram_bot
