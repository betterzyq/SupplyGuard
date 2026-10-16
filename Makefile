.PHONY: up down logs local-up local-down local-status local-restart api dev-check format lint migrate migration seed check-authz ingest-seed-docs smoke-mvp3 build-graph smoke-graphrag smoke-memory inspect-graph inspect-memory generate-eval bench smoke-benchmark smoke-observability smoke-tools smoke-llm-provider load-test-chat load-test-rag load-test-graph web web-install profile-data normalize-data load-real-data build-real-graph generate-real-docs ingest-real-docs

COMPOSE = docker compose -f infra/docker-compose.yml

# Forward extra goals as script CLI args, e.g.:
#   make build-real-graph --reset-graph --limit 5000
# GNU Make treats tokens after "make target" as additional goals; swallow them here.
REAL_DATA_TARGETS := profile-data normalize-data load-real-data build-real-graph generate-real-docs ingest-real-docs
ifneq (,$(filter $(REAL_DATA_TARGETS),$(MAKECMDGOALS)))
  REAL_DATA_ARGS := $(filter-out $(REAL_DATA_TARGETS),$(MAKECMDGOALS))
  $(eval $(REAL_DATA_ARGS):;@:)
endif

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

local-up:
	bash scripts/local_infra.sh up

local-down:
	bash scripts/local_infra.sh down

local-status:
	bash scripts/local_infra.sh status

local-restart:
	bash scripts/local_infra.sh restart

api:
	uv run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

dev-check:
	uv run python scripts/dev_check.py

migrate:
	uv run alembic upgrade head

migration:
	uv run alembic revision --autogenerate -m "$(name)"

seed:
	uv run python scripts/seed_db.py

check-authz:
	uv run python scripts/check_authz.py

ingest-seed-docs:
	uv run python scripts/ingest_seed_docs.py

smoke-mvp3:
	uv run python scripts/smoke_test_mvp3.py

build-graph:
	uv run python scripts/build_supply_graph.py

smoke-graphrag:
	uv run python scripts/smoke_test_graphrag.py

smoke-memory:
	uv run python scripts/smoke_test_memory.py

inspect-graph:
	uv run python scripts/inspect_graph.py

inspect-memory:
	uv run python scripts/inspect_memory.py

generate-eval:
	uv run python scripts/generate_eval_dataset.py

bench:
	uv run python scripts/run_benchmark.py --mode all --limit 100

smoke-benchmark:
	uv run python scripts/smoke_test_benchmark.py

smoke-observability:
	uv run python scripts/smoke_test_observability.py

smoke-tools:
	uv run python scripts/smoke_test_tools.py

smoke-llm-provider:
	uv run python scripts/smoke_test_llm_provider.py

load-test-chat:
	uv run python scripts/load_test.py --endpoint chat --concurrency 10 --requests 100 --role procurement_manager

load-test-rag:
	uv run python scripts/load_test.py --endpoint rag --concurrency 10 --requests 100 --role procurement_manager

load-test-graph:
	uv run python scripts/load_test.py --endpoint graphrag --concurrency 10 --requests 50 --role procurement_manager

web-install:
	cd apps/web && npm install

web:
	cd apps/web && npm run dev

profile-data:
	uv run python scripts/profile_external_datasets.py $(REAL_DATA_ARGS)

normalize-data:
	uv run python scripts/normalize_external_data.py $(REAL_DATA_ARGS)

load-real-data:
	uv run python scripts/load_real_data.py $(REAL_DATA_ARGS)

build-real-graph:
	uv run python scripts/build_real_supply_graph.py $(REAL_DATA_ARGS)

generate-real-docs:
	uv run python scripts/generate_realistic_documents.py $(REAL_DATA_ARGS)

ingest-real-docs:
	uv run python scripts/ingest_real_docs.py $(REAL_DATA_ARGS)

format:
	uv run black apps packages scripts
	uv run ruff check --fix apps packages scripts

lint:
	uv run ruff check apps packages scripts
