.PHONY: bootstrap test-unit test-builder-render test-all act-unit act-smoke check-act clean

PYTHON ?= python3

bootstrap:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install pre-commit
	pre-commit install
	pre-commit install --hook-type commit-msg

check-act:
	@command -v act >/dev/null 2>&1 || (echo "act no esta instalado" && exit 1)

test-unit:
	uv run --with pytest --with jinja2 pytest -q tests/unit/test_quality_builder.py

test-builder-render:
	@TMP_DIR=$$(mktemp -d); \
	cp tests/fixtures/quality_report/ruff.json $$TMP_DIR/ruff.json; \
	cp tests/fixtures/quality_report/pyright.json $$TMP_DIR/pyright.json; \
	cp tests/fixtures/quality_report/junit.xml $$TMP_DIR/junit.xml; \
	cp tests/fixtures/quality_report/coverage.json $$TMP_DIR/coverage.json; \
	cp tests/fixtures/quality_report/bandit.json $$TMP_DIR/bandit.json; \
	cp tests/fixtures/quality_report/command_status.tsv $$TMP_DIR/command_status.tsv; \
	: > $$TMP_DIR/gh_outputs.txt; \
	uv run --with jinja2 $(PYTHON) actions/python/quality-report/src/builder.py \
	  --ruff $$TMP_DIR/ruff.json \
	  --pyright $$TMP_DIR/pyright.json \
	  --junit $$TMP_DIR/junit.xml \
	  --coverage $$TMP_DIR/coverage.json \
	  --bandit $$TMP_DIR/bandit.json \
	  --commands $$TMP_DIR/command_status.tsv \
	  --template actions/python/quality-report/src/templates/report.md.j2 \
	  --output $$TMP_DIR/quality_report.md \
	  --summary $$TMP_DIR/quality_summary.json \
	  --outputs $$TMP_DIR/gh_outputs.txt \
	  --coverage-threshold 80 \
	  --fail-on-quality none \
	  --fail-on-security none; \
	echo "Reporte generado: $$TMP_DIR/quality_report.md"; \
	echo "Summary generado: $$TMP_DIR/quality_summary.json"; \
	echo "----- quality_report.md (preview) -----"; \
	sed -n '1,120p' $$TMP_DIR/quality_report.md

act-unit: check-act
	act pull_request -W .github/workflows/act-unit-builder.yml -e tests/act/events/pull_request.json

act-smoke: check-act
	act pull_request -W .github/workflows/act-quality-smoke.yml -e tests/act/events/pull_request.json

test-all: test-unit test-builder-render

clean:
	rm -rf .venv
