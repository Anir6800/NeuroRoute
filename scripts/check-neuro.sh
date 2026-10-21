#!/usr/bin/env bash
# Verify the local stack started by scripts/dev-neuro.sh. Exit 0 only if every check passes.
set -u
fail=0

expect() { # name url expected_status
  local code
  code=$(curl -s -o /dev/null --max-time 5 -w '%{http_code}' "$2" || true)
  if [ "$code" = "$3" ]; then echo "ok    $1 ($code)"; else echo "FAIL  $1: expected $3, got ${code:-none} ($2)"; fail=1; fi
}

expect "backend /health"                http://127.0.0.1:8001/health 200
expect "frontend index"                 http://127.0.0.1:5173/ 200
expect "frontend proxy /api/health"     http://127.0.0.1:5173/api/health 200
expect "auth emulator"                  http://127.0.0.1:9099/ 200
expect "/me rejects missing token"      http://127.0.0.1:8001/me 401

[ "$fail" = 0 ] && echo "all checks passed" || echo "checks failed"
exit "$fail"
