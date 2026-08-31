PYTHON ?= python3
IMAGE ?= omniscrape:local

.PHONY: help install lint format typecheck test coverage security skill-check benchmark build docker-build check clean

help:
	@echo "install       Install OmniScrape and development dependencies"
	@echo "lint          Run Ruff lint and formatting checks"
	@echo "format        Apply Ruff formatting and safe lint fixes"
	@echo "typecheck     Run mypy"
	@echo "test          Run the offline test suite"
	@echo "coverage      Run tests with coverage enforcement"
	@echo "security      Audit runtime dependencies and run Bandit"
	@echo "skill-check   Verify Codex and Claude skill mirrors are synchronized"
	@echo "benchmark     Write reproducible benchmark results"
	@echo "build         Build wheel and source distribution"
	@echo "docker-build  Build the production container"
	@echo "check         Run all local merge gates"

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check src tests benchmarks scripts
	$(PYTHON) -m ruff format --check src tests benchmarks scripts

format:
	$(PYTHON) -m ruff check --fix src tests benchmarks scripts
	$(PYTHON) -m ruff format src tests benchmarks scripts

typecheck:
	$(PYTHON) -m mypy src/omniscrape

test:
	$(PYTHON) -m pytest -q

coverage:
	$(PYTHON) -m pytest --cov-fail-under=90

security:
	$(PYTHON) -m pip_audit .
	$(PYTHON) -m bandit -q -r src/omniscrape

skill-check:
	$(PYTHON) scripts/sync_agent_skills.py --check

benchmark:
	$(PYTHON) benchmarks/run.py --iterations 100 --output benchmarks/results/latest.json

build:
	$(PYTHON) -m build

docker-build:
	docker build --tag $(IMAGE) .

check: lint typecheck coverage security skill-check build

clean:
	$(PYTHON) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('build', 'dist', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'htmlcov')]"
