#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# install_rate_limit_deps.sh
#
# Force-installs all dependencies needed for the rate-limiting middleware
# (slowapi, mypy, ruff) into the project's .venv virtual environment and
# verifies each installation succeeds.
#
# Usage:
#   cd /Users/shashank/devinlite
#   bash scripts/install_rate_limit_deps.sh
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"
PIP="${REPO_ROOT}/.venv/bin/pip"
PYTHON="${REPO_ROOT}/.venv/bin/python"

echo "==> Repository root : ${REPO_ROOT}"
echo "==> Python          : ${PYTHON}"
echo "==> Pip             : ${PIP}"
echo

# --------------------------------------------------------------------------
# Step 1 – upgrade pip itself
# --------------------------------------------------------------------------
echo "[1/6] Upgrading pip..."
cd "${REPO_ROOT}"
"${PIP}" install --upgrade pip
echo

# --------------------------------------------------------------------------
# Step 2 – install the three required packages
# --------------------------------------------------------------------------
echo "[2/6] Installing slowapi mypy ruff..."
"${PIP}" install slowapi mypy ruff
echo

# --------------------------------------------------------------------------
# Step 3 – verify slowapi
# --------------------------------------------------------------------------
echo "[3/6] Verifying slowapi..."
"${PYTHON}" -c 'import slowapi; print("slowapi version:", slowapi.__version__)'
echo

# --------------------------------------------------------------------------
# Step 4 – verify mypy
# --------------------------------------------------------------------------
echo "[4/6] Verifying mypy..."
"${PYTHON}" -m mypy --version
echo

# --------------------------------------------------------------------------
# Step 5 – verify ruff
# --------------------------------------------------------------------------
echo "[5/6] Verifying ruff..."
"${PYTHON}" -m ruff --version
echo

# --------------------------------------------------------------------------
# Step 6 – list installed packages (grep for the three we care about)
# --------------------------------------------------------------------------
echo "[6/6] Installed package list (filtered):"
"${PIP}" list | grep -E 'slowapi|mypy|ruff'
echo

echo "==> All dependency checks passed successfully."
