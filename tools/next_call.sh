#!/usr/bin/env bash
# Advance a replay-driven novel and print what the next call needs, in one line.
#
# For whoever is orchestrating: this deliberately prints only the request path, the response path
# and the model. It never prints the prompt, because the orchestrator must not read it — see
# .claude/skills/write-novel/SKILL.md.
#
# Usage: tools/next_call.sh novels/der-chrachen-v2 [extra storica run flags...]
#
# Exit codes are passed through from `storica run`: 0 done, 2 needs an answer, 3 malformed.

set -uo pipefail
NOVEL="${1:?usage: next_call.sh <novel_dir> [flags...]}"
shift || true
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$(mktemp)"

"$ROOT/.venv/bin/storica" run "$NOVEL" --driver replay "$@" >"$OUT" 2>&1
CODE=$?

case "$CODE" in
  0)
    grep -E "^(chapters|quarantined|novel|final audit)" "$OUT"
    echo "STATUS=done"
    ;;
  2)
    STAGE=$(grep -oE "for '[^']+'" "$OUT" | head -1 | tr -d "'" | sed "s/^for //")
    REQ=$(grep -oE '[^ ]+\.request\.md' "$OUT" | head -1)
    RESP=$(grep -oE '[^ ]+\.response\.(json|md)' "$OUT" | head -1)
    MODEL=$(grep -oE 'claude-[a-z0-9.-]+' "$REQ" | head -1)
    KIND=$([[ "$RESP" == *.md ]] && echo prose || echo json)
    echo "STAGE=$STAGE"
    echo "MODEL=$MODEL"
    echo "KIND=$KIND"
    echo "REQ=$ROOT/$REQ"
    echo "RESP=$ROOT/$RESP"
    # every call this run is waiting on (fan-outs raise several at once) — answer them in parallel
    grep -E '^  - model=' "$OUT" | sed 's/^  - /PENDING /'
    echo "STATUS=needs_answer"
    ;;
  3)
    grep -E "file:|error:" "$OUT"
    echo "STATUS=malformed"
    ;;
  *)
    tail -20 "$OUT"
    echo "STATUS=error"
    ;;
esac

rm -f "$OUT"
exit $CODE
