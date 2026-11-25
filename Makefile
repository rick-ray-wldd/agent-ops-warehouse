# make all       -> the whole pipeline (needs `make venv` once)
# make generate  -> synthetic data + answer key (standard library only, works without the venv)
VENV ?= $(HOME)/.venvs/agent-ops-warehouse

.PHONY: all generate test-generator venv build exercises docs clean

all:
	sh scripts/run_pipeline.sh

generate:
	python3 -I generator/generate.py

test-generator:
	python3 -I -m unittest discover -s tests -v

venv:  # downloads ~44 MB from PyPI; only after the owner has approved it
	/opt/homebrew/bin/python3.12 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

build:
	python3 -I scripts/land.py --all
	$(VENV)/bin/dbt build --profiles-dir .

exercises:
	$(VENV)/bin/python exercises/grade.py

docs:
	$(VENV)/bin/dbt docs generate --profiles-dir .

clean:
	rm -rf data target logs warehouse.duckdb warehouse.duckdb.wal
