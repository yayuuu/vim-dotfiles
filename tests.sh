#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

passed=0
for test in tests/*.py; do
  [[ "$test" == "tests/ui.py" ]] && continue
  printf '\nRunning %s\n' "$test"
  /usr/bin/python3 -B "$test"
  passed=$((passed + 1))
done

printf '\nAll %s test scripts passed.\n' "$passed"
