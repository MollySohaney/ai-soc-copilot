# Purpose: Provide the minimal command set for the local demo path.
#
# Nothing here is required to run the project. Every target is a thin wrapper
# around a command documented in README.md, so you can always run the underlying
# command directly instead.

PYTHON ?= python
DEMO_USERNAME ?= demo-admin

.DEFAULT_GOAL := help
.PHONY: help install db-up db-down migrate seed admin setup pipeline api ui smoke test reset

help: ## Show the available targets
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  First run:  cp .env.example .env && make setup"
	@echo "  Then:       make api   (one terminal)"
	@echo "              make ui    (another terminal)"
	@echo "              make smoke (a third, to verify)"

install: ## Install pinned dependencies into the active environment
	$(PYTHON) -m pip install -r requirements.txt

db-up: ## Start PostgreSQL and wait for its health check
	docker compose up -d --wait

db-down: ## Stop PostgreSQL, keeping the data volume
	docker compose down

migrate: ## Apply database migrations
	$(PYTHON) -m alembic upgrade head

seed: ## Load the deterministic demo dataset (idempotent)
	$(PYTHON) -m db.seed

admin: ## Create the demo admin account (idempotent; prints a password once if DEMO_PASSWORD is unset)
	$(PYTHON) -m db.bootstrap_user --username $(DEMO_USERNAME) --role admin --generate-password

setup: db-up migrate seed admin ## Take a clean machine to a seeded, ready database
	@echo ""
	@echo "Database is ready. Start the two processes with 'make api' and 'make ui'."

pipeline: ## Run fixture telemetry ingestion and detection execution over the API
	$(PYTHON) -m scripts.demo_pipeline --username $(DEMO_USERNAME)

api: ## Run the FastAPI service on port 8000
	$(PYTHON) -m uvicorn api.main:app --reload --port 8000

ui: ## Run the Streamlit frontend on port 8501
	$(PYTHON) -m streamlit run app/main.py

smoke: ## Verify the whole stack in one command
	$(PYTHON) -m scripts.smoke --username $(DEMO_USERNAME)

test: ## Run the full test suite
	$(PYTHON) -m pytest -q

reset: ## Delete every application row and reseed (local and demo environments only)
	$(PYTHON) -m db.reset_demo --confirm-database $${POSTGRES_DB:-ai_soc_copilot}
