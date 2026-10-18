#!/usr/bin/env bash
# Usage: scripts/verify.sh M1   -> runs Codex as verifier on everything since the last verified tag.
set -uo pipefail
M="${1:?usage: scripts/verify.sh M1}"
cd "$(git rev-parse --show-toplevel)"
BASE=$(git describe --tags --abbrev=0 --match '*-verified' 2>/dev/null || git rev-list --max-parents=0 HEAD)
ROUND=$(( $(git log --oneline "$BASE"..HEAD | grep -c "$M: fix round") + 1 ))
PROMPT="$(cat prompts/verify.md)
Milestone: $M. Round: $ROUND. Spec: prompts/$M.md. Diff to review: git diff $BASE..HEAD"
command -v codex >/dev/null || { echo "codex not installed"; exit 2; }
codex exec --full-auto "$PROMPT" > .codex_last.log 2>&1 || { echo "codex failed, see .codex_last.log"; tail -20 .codex_last.log; exit 2; }
# Enforce the verifier's write scope: revert edits outside REVIEW.md and tests/review/.
BAD=$(git diff --name-only | grep -vE '^(REVIEW\.md|tests/review/)' || true)
if [ -n "$BAD" ]; then echo "Reverting Codex edits outside its scope:"; echo "$BAD"; echo "$BAD" | xargs git checkout -- ; fi
NEW=$(git ls-files --others --exclude-standard | grep -vE '^(REVIEW\.md|tests/review/|\.codex_last\.log)' || true)
[ -n "$NEW" ] && { echo "Codex created files outside its scope (left untouched, review them):"; echo "$NEW"; }
grep -m1 '^VERDICT:' REVIEW.md || { echo "No VERDICT line in REVIEW.md"; exit 3; }
git add REVIEW.md tests/review 2>/dev/null; git commit -qm "$M: review round $ROUND" || true
grep -q '^VERDICT: PASS' REVIEW.md
