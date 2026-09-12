#!/bin/zsh
# Окружение для итогового проекта (macOS, Apple Silicon).
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "Ставлю uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

uv python install 3.12
uv venv .venv --python 3.12
uv pip install --python .venv -r requirements.txt ipykernel notebook
.venv/bin/python -m ipykernel install --user --name realty --display-name "realty-3.12"

echo
echo "Готово. Дальше:"
echo "  source .venv/bin/activate"
echo "  jupyter notebook notebooks/final_project_rubinshtein.ipynb"
echo "Kernel: realty-3.12 → Restart & Run All"
