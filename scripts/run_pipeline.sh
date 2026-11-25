#!/bin/sh
# One command, generate -> land -> build -> incremental -> full-refresh comparison -> tests.
# Needs the venv from `make venv` (duckdb, dbt-core, dbt-duckdb). Exits non-zero on the first failure.
set -eu
cd "$(dirname "$0")/.."
VENV=${VENV:-$HOME/.venvs/agent-ops-warehouse}
PY="$VENV/bin/python"
export DO_NOT_TRACK=1 DBT_SEND_ANONYMOUS_USAGE_STATS=false
DBT="$VENV/bin/dbt"
FIRST_LOAD_THROUGH=${FIRST_LOAD_THROUGH:-2025-02-14}

echo "== 1. generate synthetic data and the answer key"
python3 -I generator/generate.py
python3 -I -m unittest discover -s tests

echo "== 2. first load: batches through $FIRST_LOAD_THROUGH, full build"
rm -f warehouse.duckdb
python3 -I scripts/land.py --reset --through "$FIRST_LOAD_THROUGH"
$DBT run --profiles-dir . --full-refresh
echo "after first load: $("$PY" scripts/checksum.py fct_event)"

echo "== 3. the rest of the batches arrive: incremental run"
python3 -I scripts/land.py --all
$DBT run --profiles-dir .
INCREMENTAL=$("$PY" scripts/checksum.py fct_event)

echo "== 4. full refresh must give the same fact table"
$DBT run --profiles-dir . --full-refresh
FULL=$("$PY" scripts/checksum.py fct_event)
echo "incremental: $INCREMENTAL"
echo "full:        $FULL"
[ "$INCREMENTAL" = "$FULL" ] || { echo "FAIL: incremental and full refresh differ"; exit 1; }

echo "== 5. data-quality and reference tests"
$DBT test --profiles-dir .

echo "== 6. exercise grader, end to end on the built warehouse"
"$PY" -m unittest discover -s tests -p test_grader.py -v
echo "PIPELINE OK"
