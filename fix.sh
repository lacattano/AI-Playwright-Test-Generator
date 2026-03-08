#!/bin/bash
set -e

echo ">>> ruff fix..."
ruff check . --fix

echo ">>> ruff format..."
ruff format .

echo ">>> mypy..."
mypy streamlit_app.py src/

echo ">>> All checks passed"