.PHONY: up down logs local-up local-down local-status local-restart api dev-check format lint migrate migration seed check-authz ingest-seed-docs smoke-mvp3 build-graph smoke-graphrag smoke-memory inspect-graph inspect-memory generate-eval bench smoke-benchmark smoke-observability smoke-tools smoke-llm-provider load-test-chat load-test-rag load-test-graph web web-install profile-data normalize-data load-real-data build-real-graph generate-real-docs ingest-real-docs

COMPOSE = docker compose -f infra/docker-compose.yml

.PHONY: phase1-check phase1-smoke phase1-browser phase2-check phase2-smoke phase2-browser acceptance-up acceptance-down acceptance-status
.PHONY: phase3-check phase3-smoke phase3-browser phase3-snapshot-check
phase3-snapshot-check:
	.venv/bin/python scripts/inspect_simulation.py --latest

phase3-check:
	.venv/bin/python scripts/phase3_check.py

phase3-smoke:
	.venv/bin/python scripts/phase3_smoke.py

phase3-browser:
	.venv/bin/python scripts/phase3_check.py --browser

phase2-check:
	.venv/bin/python scripts/phase2_check.py

phase2-smoke:
	.venv/bin/python scripts/phase2_smoke.py

phase2-browser:
	.venv/bin/python scripts/phase2_check.py --browser

phase1-check:
	.venv/bin/python scripts/phase1_check.py

phase1-smoke:
	.venv/bin/python scripts/phase1_smoke.py

phase1-browser:
	.venv/bin/python scripts/phase1_check.py --browser

acceptance-up:
	.venv/bin/python scripts/acceptance_services.py up

acceptance-down:
	.venv/bin/python scripts/acceptance_services.py down

acceptance-status:
	.venv/bin/python scripts/acceptance_services.py status

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
	@echo "已禁用破坏性旧种子入口。演示账号请运行 .venv/bin/python scripts/prepare_phase1_demo.py（增量幂等）。"
	@exit 2

check-authz:
	DEBUG=false .venv/bin/python scripts/check_authz.py

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

.PHONY: phase4-data phase4-data-check phase4-train phase4-reproduce phase4-check phase4-smoke phase4-browser phase4-audit
phase4-data:
	.venv/bin/python scripts/fetch_phase4_data.py
phase4-data-check:
	.venv/bin/python scripts/fetch_phase4_data.py --check-only
phase4-train:
	.venv/bin/python scripts/phase4_train.py
phase4-reproduce:
	.venv/bin/python scripts/phase4_train.py --reproduce
phase4-check:
	.venv/bin/python scripts/phase4_check.py
phase4-smoke:
	.venv/bin/python scripts/phase4_smoke.py
phase4-browser:
	.venv/bin/python scripts/phase4_check.py --browser
phase4-audit:
	.venv/bin/python scripts/phase4_audit.py

.PHONY: phase5-check phase5-db-apply phase5-smoke phase5-browser phase5-audit
phase5-check:
	.venv/bin/python scripts/phase5_check.py
phase5-db-apply:
	.venv/bin/python scripts/phase5_db.py apply
phase5-smoke:
	.venv/bin/python scripts/phase5_smoke.py
phase5-browser:
	.venv/bin/python scripts/phase5_check.py --browser
phase5-audit:
	.venv/bin/python scripts/phase5_audit.py

.PHONY: phase6-check phase6-smoke phase6-browser phase6-regression phase6-audit
phase6-check:
	.venv/bin/python scripts/phase6_check.py
phase6-smoke:
	.venv/bin/python scripts/phase6_smoke.py
phase6-browser:
	.venv/bin/python scripts/phase6_check.py --browser
phase6-regression:
	.venv/bin/python scripts/phase6_check.py --regression
phase6-audit:
	.venv/bin/python scripts/phase6_audit.py
