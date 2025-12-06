.PHONY lint:
lint:
	@uvx ruff check .

.PHONY fmt:
fmt:
	@uvx ruff check --fix .
	@uvx ruff format .

.PHONY typecheck:
typecheck:
	@uvx mypy .
