#!/bin/bash
set -e

echo ">>> ruff fix..."
ruff check . --fix

echo ">>> ruff format..."
ruff format .

echo ">>> mypy..."
mypy app/

echo ">>> pytest..."
pytest -v

echo ""
echo "All checks passed!"
