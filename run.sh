#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Bahraini 28 — local development runner (hot reload, one command).
#
#   ./run.sh                  API on :8000 + SPA on :5173, both watched
#   ./run.sh --seed           ...plus demo businesses + a volunteer login
#   ./run.sh --areas          ...plus the real Bahrain area list (idempotent)
#   ./run.sh --backend-only   just the API, logs live in this terminal
#   ./run.sh --frontend-only  just the SPA dev server (API expected elsewhere)
#   ./run.sh --help
#
# Ctrl-C stops everything this script started. There is no build step: uvicorn
# reloads on Python changes, Vite HMRs the SPA in place.
#
# Env overrides:  WEB_PORT=5173  API_PORT=8000  NO_INSTALL=1
#
# Deliberately bash 3.2 compatible (macOS ships 3.2 at /bin/bash).
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
NO_INSTALL="${NO_INSTALL:-0}"

# frontend/vite.config.ts proxies /api and /uploads to a hard-coded
# http://localhost:8000, so a non-default API_PORT breaks the SPA proxy.
PROXY_TARGET_PORT=8000

RUN_BACKEND=1
RUN_WEB=1
SEED=0
SEED_AREAS=0

PY=""
# ${TMPDIR} on macOS ends with a slash; strip it so the printed path is clean.
TMP="${TMPDIR:-/tmp}"
API_LOG="${TMP%/}/bahraini28-api.log"
STARTED_API_PID=""
STARTED_SPA_PID=""

# --- output helpers ---------------------------------------------------------
if [ -t 1 ]; then
  C_STEP=$'\033[1;36m'; C_OK=$'\033[1;32m'; C_WARN=$'\033[1;33m'
  C_ERR=$'\033[1;31m'; C_DIM=$'\033[2m'; C_RESET=$'\033[0m'
else
  C_STEP=; C_OK=; C_WARN=; C_ERR=; C_DIM=; C_RESET=
fi

step() { printf '%s==> %s%s\n' "$C_STEP" "$*" "$C_RESET"; }
info() { printf '    %s\n' "$*"; }
dim()  { printf '    %s%s%s\n' "$C_DIM" "$*" "$C_RESET"; }
ok()   { printf '%s  ok%s  %s\n' "$C_OK" "$C_RESET" "$*"; }
warn() { printf '%swarn%s  %s\n' "$C_WARN" "$C_RESET" "$*" >&2; }
die()  { printf '%sfail%s  %s\n' "$C_ERR" "$C_RESET" "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Bahraini 28 — local dev runner (hot reload)

Usage: ./run.sh [options]

  (no options)        Start the API (:8000) and the SPA dev server (:5173).
                      The SPA logs live here; the API logs go to a file
                      (path is printed at startup).
  --backend-only      Start only the API, with its logs live in this terminal.
  --frontend-only     Start only the SPA (use when an API already runs on
                      :8000 outside this script).
  --seed              Run backend/scripts/seed.py first (demo businesses and a
                      volunteer account: volunteer@example.com / volunteer123).
  --areas             Run backend/scripts/seed_areas.py first (imports the
                      real Bahrain area list; idempotent).
  --no-install        Never install anything; fail if deps are missing.
  --web-port PORT     SPA port (default 5173).
  -h, --help          This text.

Environment: API_PORT (8000), WEB_PORT (5173), NO_INSTALL=1

URLs once running:
  SPA   http://127.0.0.1:5173
  API   http://127.0.0.1:8000        (OpenAPI docs at /docs)
  Admin admin / admin123             (dev bootstrap account)
EOF
}

# --- small utilities --------------------------------------------------------
# PID listening on a TCP port, or empty when the port is free.
port_pid() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -n 1; }

http_ok() { curl -fsS --max-time 2 "$1" >/dev/null 2>&1; }

# Poll an HTTP endpoint. Tries are 0.5 s apart, e.g. 180 tries ~= 90 s.
wait_http() {
  local url="$1" tries="${2:-180}" i=1
  while [ "$i" -le "$tries" ]; do
    if http_ok "$url"; then return 0; fi
    sleep 0.5
    i=$((i + 1))
  done
  return 1
}

# --- shutdown ---------------------------------------------------------------
# Both tools fork children (uvicorn: reloader + worker, npm: node + vite), so
# kill the whole tree instead of just the PID we launched.
kill_tree() {
  local sig="$1" pid="$2" child
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_tree "$sig" "$child"
  done
  kill -s "$sig" "$pid" 2>/dev/null || true
}

port_holder_hint() {
  local port="$1" pid
  pid="$(port_pid "$port")" || true
  if [ -n "$pid" ]; then
    printf 'port %s is held by pid %s (%s)\n' \
      "$port" "$pid" "$(ps -p "$pid" -o comm= 2>/dev/null || echo '?')"
  fi
}

# `kill -0` still succeeds for a zombie, which would make the shutdown wait
# below burn its full timeout on an already-dead process. Check the state.
proc_alive() {
  local state
  state="$(ps -o state= -p "$1" 2>/dev/null | tr -d ' ' || true)"
  [ -n "$state" ] && [ "${state#Z}" = "$state" ]
}

# Stop a child we launched. On a terminal Ctrl-C the whole process group has
# already received SIGINT and both servers exit cleanly on their own, so wait
# first — that keeps the terminal free of "Terminated" job chatter. Escalate
# TERM, then KILL, only for signals the children never saw (e.g. `kill <pid>`).
stop_child() {
  local pid="$1" i=0
  while [ "$i" -lt 8 ] && proc_alive "$pid"; do
    sleep 0.25
    i=$((i + 1))
  done
  if proc_alive "$pid"; then
    kill_tree TERM "$pid"
    i=0
    while [ "$i" -lt 20 ] && proc_alive "$pid"; do
      sleep 0.25
      i=$((i + 1))
    done
  fi
  if proc_alive "$pid"; then
    info "pid $pid ignored SIGTERM — sending SIGKILL"
    kill_tree KILL "$pid"
  fi
}

cleanup() {
  local code=$? sig="${1:-}" i=0 port

  # Clear the traps first so a second Ctrl-C can't re-enter this function.
  trap - EXIT INT TERM HUP

  if [ -n "$STARTED_SPA_PID" ] || [ -n "$STARTED_API_PID" ]; then
    printf '\n'
    info "shutting down..."
  fi

  # SPA first: it is the one talking to the API.
  if [ -n "$STARTED_SPA_PID" ]; then
    stop_child "$STARTED_SPA_PID"
  fi
  if [ -n "$STARTED_API_PID" ]; then
    stop_child "$STARTED_API_PID"
  fi

  # A quick re-run should not trip over a socket still being released.
  for port in "$API_PORT" "$WEB_PORT"; do
    i=0
    while [ "$i" -lt 20 ] && [ -n "$(port_pid "$port")" ]; do
      sleep 0.25
      i=$((i + 1))
    done
  done

  if [ -n "$STARTED_API_PID" ] && [ "$RUN_WEB" = 1 ]; then
    dim "stopped. API log kept at $API_LOG"
  fi

  if [ -n "$sig" ]; then
    code="$sig"
  fi
  exit "$code"
}
trap 'cleanup' EXIT
trap 'cleanup 130' INT
trap 'cleanup 143' TERM HUP

# --- environment checks -----------------------------------------------------
# Same venv precedence as deploy/deploy.sh: repo-level .venv, then backend/.venv.
find_python() {
  if [ -x "$ROOT/.venv/bin/python" ]; then
    PY="$ROOT/.venv/bin/python"
  elif [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
    PY="$BACKEND_DIR/.venv/bin/python"
  fi
}

check_python() {
  find_python

  if [ -z "$PY" ]; then
    if [ "$NO_INSTALL" = 1 ]; then
      die "no virtualenv found and NO_INSTALL=1 (create one: python3 -m venv .venv)"
    fi
    step "No virtualenv found — creating .venv"
    command -v python3 >/dev/null 2>&1 || die "python3 not found on PATH"
    python3 -m venv "$ROOT/.venv"
    PY="$ROOT/.venv/bin/python"
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip install --quiet -r "$BACKEND_DIR/requirements-dev.txt"
  fi

  # Import probe beats `pip list`: it fails on a half-built or broken venv too.
  if ! "$PY" -c 'import fastapi, uvicorn, sqlalchemy, pydantic' >/dev/null 2>&1; then
    if [ "$NO_INSTALL" = 1 ]; then
      die "backend deps missing in $PY and NO_INSTALL=1"
    fi
    step "Installing backend dependencies (requirements-dev.txt)"
    "$PY" -m pip install --quiet -r "$BACKEND_DIR/requirements-dev.txt"
  fi

  ok "python: $("$PY" -V 2>&1)"
}

check_node() {
  command -v node >/dev/null 2>&1 || die "node not found (Vite 6 needs Node 18+)"
  command -v npm >/dev/null 2>&1 || die "npm not found"

  local major
  major="$(node -v | sed 's/^v//' | cut -d. -f1)"
  [ "$major" -ge 18 ] 2>/dev/null || die "Node $(node -v) is too old for Vite 6 (need 18+)"

  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    if [ "$NO_INSTALL" = 1 ]; then
      die "frontend/node_modules missing and NO_INSTALL=1"
    fi
    step "Installing frontend dependencies"
    # `npm ci` when a lockfile exists: reproducible and it never rewrites the
    # lockfile. Falls back to `npm install` if the lockfile is out of sync.
    if [ -f "$FRONTEND_DIR/package-lock.json" ]; then
      (cd "$FRONTEND_DIR" && npm ci) || (cd "$FRONTEND_DIR" && npm install)
    else
      (cd "$FRONTEND_DIR" && npm install)
    fi
  fi

  ok "node: $(node -v) / npm $(npm -v)"
}

# Settings are read from the directory uvicorn is launched in, so this is
# backend/.env (README: `cp .env.example .env`). Never overwrite an existing one.
ensure_backend_env() {
  if [ -f "$BACKEND_DIR/.env" ]; then
    dim "using existing backend/.env"
    return
  fi
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  info "created backend/.env from .env.example (SQLite dev DB, admin/admin123)"
}

require_free_port() {
  local port="$1" remedy="$2"
  if [ -n "$(port_pid "$port")" ]; then
    port_holder_hint "$port" >&2
    die "$remedy"
  fi
}

# --- launchers --------------------------------------------------------------
start_api() {
  # --reload-dir app is load-bearing: uvicorn's default reloader watches the
  # whole cwd, and this API writes ./bahraini28.db on every request, so it
  # would reload on its own writes. Scoped to the source tree instead.
  (
    cd "$BACKEND_DIR" && exec "$PY" -m uvicorn app.main:app \
      --reload --reload-dir app \
      --host 127.0.0.1 --port "$API_PORT"
  )
}

start_spa() {
  # --host 127.0.0.1 + --strictPort mirror e2e/conftest.py: `localhost` can
  # resolve to ::1 (vite binds IPv4 only), and the port must not silently
  # drift to 5174 or every URL we print would be wrong.
  (
    cd "$FRONTEND_DIR" && exec npm run dev -- \
      --host 127.0.0.1 --port "$WEB_PORT" --strictPort
  )
}

run_backend_scripts() {
  local script="$1"
  # PYTHONPATH=. so `from app...` resolves, exactly as the README documents.
  (cd "$BACKEND_DIR" && PYTHONPATH=. "$PY" "scripts/$script")
}

# --- main -------------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --seed)          SEED=1 ;;
    --areas)         SEED_AREAS=1 ;;
    --backend-only)  RUN_WEB=0 ;;
    --frontend-only) RUN_BACKEND=0 ;;
    --no-install)    NO_INSTALL=1 ;;
    --web-port)
      shift
      [ $# -gt 0 ] || die "--web-port needs a value"
      WEB_PORT="$1"
      ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
  shift
done

if [ "$RUN_BACKEND" = 0 ] && [ "$RUN_WEB" = 0 ]; then
  die "nothing to run (--backend-only and --frontend-only cancel out)"
fi
if [ "$RUN_BACKEND" = 0 ] && { [ "$SEED" = 1 ] || [ "$SEED_AREAS" = 1 ]; }; then
  die "--seed/--areas write to the database, so they need the API side (drop --frontend-only)"
fi
if [ "$RUN_BACKEND" = 1 ] && [ "$RUN_WEB" = 1 ] && [ "$API_PORT" != "$PROXY_TARGET_PORT" ]; then
  warn "API_PORT=$API_PORT, but vite.config.ts proxies /api and /uploads to :$PROXY_TARGET_PORT"
  warn "the SPA would never reach this API — start it with API_PORT=$PROXY_TARGET_PORT"
fi

step "Checking the local environment"
if [ "$RUN_WEB" = 1 ]; then
  check_node
else
  dim "skipping frontend checks (--backend-only)"
fi
if [ "$RUN_BACKEND" = 1 ]; then
  require_free_port "$API_PORT" \
    "free port $API_PORT first (hint: --frontend-only reuses an API you started elsewhere)"
  check_python
  ensure_backend_env
else
  dim "skipping API checks (--frontend-only)"
fi
if [ "$RUN_WEB" = 1 ]; then
  require_free_port "$WEB_PORT" \
    "free port $WEB_PORT first (hint: WEB_PORT=5174 ./run.sh)"
fi

# seed.py lays down demo categories/areas/businesses, then seed_areas.py adds
# the full official area list on top (idempotent, never touches existing rows).
# Order matches README.md.
if [ "$SEED" = 1 ]; then
  step "Seeding demo data (categories, areas, businesses, volunteer login)"
  run_backend_scripts seed.py
fi
if [ "$SEED_AREAS" = 1 ]; then
  step "Importing the real Bahrain area list (idempotent)"
  run_backend_scripts seed_areas.py
fi

if [ "$RUN_BACKEND" = 1 ]; then
  if [ "$RUN_WEB" = 1 ]; then
    # Backgrounded so the SPA can own this terminal. uvicorn prints its
    # tracebacks to the log file instead, which we tail if startup fails.
    step "Starting API on :$API_PORT (hot reload)"
    : > "$API_LOG"
    start_api >>"$API_LOG" 2>&1 &
    STARTED_API_PID=$!
    if wait_http "http://127.0.0.1:$API_PORT/health" 180; then
      ok "API ready — log: $API_LOG"
    else
      warn "API did not become healthy within 90s; last log lines:"
      tail -n 30 "$API_LOG" >&2 || true
      die "full log at $API_LOG"
    fi
  else
    step "Starting API on :$API_PORT (hot reload, logs live here)"
    printf '\n'
    start_api
    exit 0
  fi
fi

if [ "$RUN_WEB" = 1 ]; then
  printf '\n'
  step "Starting SPA dev server on :$WEB_PORT (hot reload)"
  printf '\n'
  printf '    %-8s %s\n' "SPA" "http://127.0.0.1:$WEB_PORT"
  if [ "$RUN_BACKEND" = 1 ]; then
    printf '    %-8s %s\n' "API" "http://127.0.0.1:$API_PORT  (docs: /docs, log: $API_LOG)"
  else
    printf '    %-8s %s\n' "API" "expected on :$API_PORT, started outside run.sh"
  fi
  if [ "$SEED" = 1 ]; then
    printf '    %-8s %s\n' "Admin" "admin / admin123"
    printf '    %-8s %s\n' "Member" "volunteer@example.com / volunteer123"
  else
    printf '    %-8s %s\n' "Admin" "admin / admin123   (--seed adds a demo volunteer)"
  fi
  printf '\n    %s\n\n' "Edits reload in place. Ctrl-C stops everything run.sh started."
  # Run Vite as our direct child so the trap knows its PID. A bare foreground
  # command cannot be killed if we get SIGTERM instead of a terminal Ctrl-C.
  # It stays in this process group, so the terminal still delivers Ctrl-C to
  # Vite directly and its HMR output stays live in this terminal.
  start_spa &
  STARTED_SPA_PID=$!
  wait "$STARTED_SPA_PID"
  exit 0
fi
