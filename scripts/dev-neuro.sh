#!/usr/bin/env bash
# Start the whole local stack: Auth emulator (9099), backend (8001), frontend (5173).
# Everything binds to 127.0.0.1. No deployment, no Firebase Hosting.
#   scripts/dev-neuro.sh          start, stay in foreground, Ctrl-C stops everything
#   scripts/dev-neuro.sh stop     stop leftovers recorded in .dev-logs/pids
set -u
cd "$(dirname "$0")/.."
if grep -qi microsoft /proc/version 2>/dev/null; then
  echo "This is WSL bash (plain 'bash' in cmd/PowerShell), which lacks the Windows node/java/venv." >&2
  echo "Use Git Bash instead, or from cmd/PowerShell:" >&2
  echo '  "C:\Program Files\Git\bin\bash.exe" scripts/dev-neuro.sh' >&2
  exit 1
fi
LOGS=.dev-logs
PIDS=$LOGS/pids
mkdir -p "$LOGS"

if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
else PY=""; fi

kill_tree() { # $1 = pid from $!; on Git Bash kill the whole native process tree
  local win
  win=$(cat "/proc/$1/winpid" 2>/dev/null || true)
  if [ -n "$win" ] && command -v taskkill >/dev/null 2>&1; then
    taskkill //F //T //PID "$win" >/dev/null 2>&1 || true
  else
    kill "$1" 2>/dev/null || true
  fi
}

stop_all() {
  [ -f "$PIDS" ] || return 0
  while read -r pid; do [ -n "$pid" ] && kill_tree "$pid"; done <"$PIDS"
  rm -f "$PIDS"
}

if [ "${1:-start}" = "stop" ]; then stop_all; echo "stopped"; exit 0; fi

port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
wait_http() { # url name timeout_s
  for _ in $(seq 1 "$3"); do
    curl -s -o /dev/null --max-time 2 "$1" && return 0
    sleep 1
  done
  echo "FAILED: $2 did not answer at $1 within $3 s (see $LOGS/)" >&2
  return 1
}

# Prerequisites (fail early with a clear message)
missing=0
[ -n "$PY" ] || { echo "missing: .venv (see docs/setup/run-local.md)" >&2; missing=1; }
for tool in node npm curl firebase java; do
  command -v "$tool" >/dev/null 2>&1 || { echo "missing: $tool" >&2; missing=1; }
done
[ -d frontend/node_modules ] || { echo "missing: frontend/node_modules (run: npm install --prefix frontend)" >&2; missing=1; }
for p in 9099 8001 5173; do
  port_busy "$p" && { echo "port $p already in use (run: scripts/dev-neuro.sh stop)" >&2; missing=1; }
done
[ "$missing" = 0 ] || exit 1

: >"$PIDS"
RUNNING=()
trap 'echo; echo "stopping..."; stop_all; exit 0' INT TERM
trap stop_all EXIT

firebase emulators:start --only auth --project demo-neuroroute >"$LOGS/emulator.log" 2>&1 &
echo $! >>"$PIDS"; RUNNING+=("$!")
wait_http http://127.0.0.1:9099/ "Auth emulator" 60 || exit 1

(cd backend && exec "../$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8001) >"$LOGS/backend.log" 2>&1 &
echo $! >>"$PIDS"; RUNNING+=("$!")
wait_http http://127.0.0.1:8001/health "backend" 30 || exit 1

npm --prefix frontend run dev >"$LOGS/frontend.log" 2>&1 &
echo $! >>"$PIDS"; RUNNING+=("$!")
wait_http http://127.0.0.1:5173/ "frontend" 30 || exit 1

"$PY" scripts/seed_emulator_user.py || { echo "seeding test user failed" >&2; exit 1; }

cat <<'EOF'

NeuroRoute is up (local only):
  app       http://127.0.0.1:5173        (login: dev@neuroroute.test / devpass123)
  backend   http://127.0.0.1:8001/health
  emulator  http://127.0.0.1:9099
  logs      .dev-logs/    verify: scripts/check-neuro.sh    stop: Ctrl-C
EOF
# Stay up while all three services live; exit (and clean up) as soon as one dies.
while sleep 2; do
  for pid in "${RUNNING[@]}"; do
    kill -0 "$pid" 2>/dev/null || { echo "a service exited; see $LOGS/" >&2; exit 1; }
  done
done
