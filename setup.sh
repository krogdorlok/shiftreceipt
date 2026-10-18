#!/usr/bin/env bash
# Run once on the Mac:  cd ~/Desktop/projects/ShiftReceipt && bash setup.sh
set -euo pipefail
PY=$(command -v python3.12 || command -v python3.13 || command -v python3)
"$PY" -c 'import sys; assert sys.version_info >= (3, 10), "need Python 3.10+"' || exit 1
echo "Using $($PY --version)"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m pytest -q
[ -f .env ] || { cp .env.example .env; echo "Created .env: fill in the keys before M1"; }
[ -d .git ] || { git init -q -b main; git add -A; git commit -qm "Core: models, diff, rules, parser, db (88 tests)"; git tag core-verified; }
if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  gh repo view >/dev/null 2>&1 || gh repo create shiftreceipt --private --source . --push
  echo "GitHub repo ready (private until submission: gh repo edit --visibility public --accept-visibility-change-consequences)"
else
  echo "gh not logged in: run 'gh auth login' then 'gh repo create shiftreceipt --private --source . --push'"
fi
command -v codex >/dev/null && echo "codex: $(codex --version 2>/dev/null)" || echo "codex CLI missing: npm i -g @openai/codex"
command -v claude >/dev/null && echo "claude: $(claude --version 2>/dev/null)" || echo "claude CLI missing"
echo "Done. Next: open Claude Code here and paste prompts/M1.md"
