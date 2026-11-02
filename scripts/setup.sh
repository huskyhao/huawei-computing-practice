#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs models results
if ! python3 -m venv .venv; then
  mkdir -p tools
  curl -fL --connect-timeout 15 --max-time 180 https://bootstrap.pypa.io/virtualenv.pyz -o tools/virtualenv.pyz
  sha256sum tools/virtualenv.pyz | tee logs/virtualenv-sha256.txt
  python3 tools/virtualenv.pyz --no-periodic-update .venv 2>&1 | tee logs/virtualenv.log
fi
.venv/bin/python -m pip install --disable-pip-version-check --index-url https://pypi.org/simple -r requirements.txt 2>&1 | tee logs/setup.log
.venv/bin/python -m pip check | tee logs/pip-check.log
.venv/bin/python -m pip freeze > results/requirements-resolved.txt
