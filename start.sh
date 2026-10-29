#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
log_dir="$project_root/logs"
backend_log="$log_dir/backend.log"
frontend_log="$log_dir/frontend.log"

read_dotenv_value() {
    local key="$1"
    local value=""

    if [[ -f "$project_root/.env" ]]; then
        value="$(sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*([^[:space:]#]+).*/\1/p" "$project_root/.env" | head -n 1)"
    fi

    printf '%s' "$value"
}

configured_value() {
    local key="$1"
    local fallback="$2"
    local value="${!key:-}"

    if [[ -z "$value" ]]; then
        value="$(read_dotenv_value "$key")"
    fi

    printf '%s' "${value:-$fallback}"
}

backend_port="$(configured_value BACKEND_PORT 8483)"
frontend_port="${VITE_FRONTEND_PORT:-}"
if [[ -z "$frontend_port" ]]; then
    frontend_port="$(read_dotenv_value VITE_FRONTEND_PORT)"
fi
frontend_port="${frontend_port:-3015}"
startup_timeout="${STARTUP_TIMEOUT:-60}"

case "$backend_port" in
    ''|*[!0-9]*) printf 'Invalid BACKEND_PORT: %s\n' "$backend_port" >&2; exit 1 ;;
esac
case "$frontend_port" in
    ''|*[!0-9]*) printf 'Invalid VITE_FRONTEND_PORT: %s\n' "$frontend_port" >&2; exit 1 ;;
esac
case "$startup_timeout" in
    ''|*[!0-9]*) printf 'Invalid STARTUP_TIMEOUT: %s\n' "$startup_timeout" >&2; exit 1 ;;
esac

backend_url="http://127.0.0.1:${backend_port}/api/sys_check"
frontend_url="http://127.0.0.1:${frontend_port}/"

backend_pid=""
frontend_pid=""
backend_group=""
frontend_group=""
cleanup_done=0

log() {
    printf '[start] %s\n' "$*"
}

http_ready() {
    local url="$1"
    curl --noproxy '*' -fsS --max-time 2 -o /dev/null "$url" >/dev/null 2>&1
}

frontend_http_ready() {
    local page

    page="$(curl --noproxy '*' -fsS --max-time 2 "$frontend_url" 2>/dev/null)" || return 1
    [[ "$page" == *BiliNote* ]]
}

port_listening() {
    local port="$1"

    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | grep -q .
        return
    fi

    if command -v ss >/dev/null 2>&1; then
        ss -ltnH 2>/dev/null | awk -v port=":$port" '$4 ~ port "$" { found = 1 } END { exit(found ? 0 : 1) }'
        return
    fi

    return 1
}

show_port_owner() {
    local port="$1"

    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sed -n '1,5p'
    elif command -v ss >/dev/null 2>&1; then
        ss -ltnp 2>/dev/null | sed -n '1,8p'
    fi
}

pid_alive() {
    kill -0 "$1" 2>/dev/null || return 1
    local state

    state="$(ps -o stat= -p "$1" 2>/dev/null)" || return 1
    [[ "$state" != Z* ]]
}

group_alive() {
    kill -0 -- "-$1" 2>/dev/null
}

stop_process() {
    local name="$1"
    local pid="$2"
    local group="$3"
    local i

    [[ -n "$pid" ]] || return 0

    if [[ -n "$group" ]]; then
        group_alive "$group" || return 0
        log "Stopping $name (process group $group)"
        kill -TERM -- "-$group" 2>/dev/null || true
    else
        pid_alive "$pid" || return 0
        log "Stopping $name (pid $pid)"
        kill -TERM "$pid" 2>/dev/null || true
    fi

    for i in {1..50}; do
        if [[ -n "$group" ]]; then
            group_alive "$group" || return 0
        else
            pid_alive "$pid" || return 0
        fi
        sleep 0.1
    done

    if [[ -n "$group" ]]; then
        kill -KILL -- "-$group" 2>/dev/null || true
    elif pid_alive "$pid"; then
        kill -KILL "$pid" 2>/dev/null || true
    fi
}

cleanup() {
    local status=$?

    if ((cleanup_done)); then
        return
    fi
    cleanup_done=1
    trap - EXIT INT TERM

    stop_process "frontend" "$frontend_pid" "$frontend_group"
    stop_process "backend" "$backend_pid" "$backend_group"
    exit "$status"
}

show_log_tail() {
    local name="$1"
    local file="$2"

    [[ -f "$file" ]] || return 0
    printf '\n--- %s log (last 40 lines) ---\n' "$name" >&2
    tail -n 40 "$file" >&2 || true
}

wait_for_service() {
    local name="$1"
    local url="$2"
    local pid="$3"
    local log_file="$4"
    local deadline=$((SECONDS + startup_timeout))

    while ((SECONDS < deadline)); do
        if http_ready "$url"; then
            log "$name is ready: $url"
            return 0
        fi

        if [[ -n "$pid" ]] && ! pid_alive "$pid"; then
            printf '%s exited before becoming ready.\n' "$name" >&2
            show_log_tail "$name" "$log_file"
            return 1
        fi
        sleep 1
    done

    printf '%s did not become ready within %ss.\n' "$name" "$startup_timeout" >&2
    show_log_tail "$name" "$log_file"
    return 1
}

start_backend() {
    : > "$backend_log"
    if command -v setsid >/dev/null 2>&1; then
        setsid bash -c 'cd "$1" && exec bash "$2"' _ "$project_root" "$project_root/backend/run.sh" \
            >"$backend_log" 2>&1 &
        backend_pid=$!
        backend_group=$backend_pid
    else
        (cd "$project_root" && exec bash backend/run.sh) >"$backend_log" 2>&1 &
        backend_pid=$!
    fi
    log "Started backend (pid $backend_pid); log: $backend_log"
}

start_frontend() {
    : > "$frontend_log"
    if command -v setsid >/dev/null 2>&1; then
        setsid bash -c 'cd "$1" && exec corepack pnpm@9.15.0 dev -- --host 0.0.0.0' _ \
            "$project_root/BillNote_frontend" >"$frontend_log" 2>&1 &
        frontend_pid=$!
        frontend_group=$frontend_pid
    else
        (
            cd "$project_root/BillNote_frontend"
            exec corepack pnpm@9.15.0 dev -- --host 0.0.0.0
        ) >"$frontend_log" 2>&1 &
        frontend_pid=$!
    fi
    log "Started frontend (pid $frontend_pid); log: $frontend_log"
}

if ! command -v curl >/dev/null 2>&1; then
    printf 'curl is required to check service readiness.\n' >&2
    exit 1
fi
if [[ ! -d "$project_root/BillNote_frontend" ]]; then
    printf 'Frontend directory not found: %s\n' "$project_root/BillNote_frontend" >&2
    exit 1
fi
if ! command -v corepack >/dev/null 2>&1; then
    printf 'corepack is required to start the frontend.\n' >&2
    exit 1
fi

mkdir -p "$log_dir"
trap cleanup EXIT INT TERM

backend_ready=0
frontend_ready=0

if http_ready "$backend_url"; then
    backend_ready=1
    log "Backend is already running; reusing it (Ctrl+C will not stop this existing process)."
elif port_listening "$backend_port"; then
    printf 'Backend port %s is occupied by a non-ready process:\n' "$backend_port" >&2
    show_port_owner "$backend_port" >&2
    exit 1
fi

if frontend_http_ready; then
    frontend_ready=1
    log "Frontend is already running; reusing it (Ctrl+C will not stop this existing process)."
elif port_listening "$frontend_port"; then
    printf 'Frontend port %s is occupied by a non-ready process:\n' "$frontend_port" >&2
    show_port_owner "$frontend_port" >&2
    exit 1
fi

if ((backend_ready == 0)); then
    start_backend
fi
if ((frontend_ready == 0)); then
    start_frontend
fi

if [[ -n "$backend_pid" ]] && ! wait_for_service "Backend" "$backend_url" "$backend_pid" "$backend_log"; then
    exit 1
fi
if [[ -n "$frontend_pid" ]] && ! wait_for_service "Frontend" "$frontend_url" "$frontend_pid" "$frontend_log"; then
    exit 1
fi

if [[ -z "$backend_pid" && -z "$frontend_pid" ]]; then
    log "Both services are already ready: http://localhost:${frontend_port}"
    exit 0
fi

log "BiliNote is available at http://localhost:${frontend_port}"
log "Press Ctrl+C to stop services started by this script."

while :; do
    if [[ -n "$backend_pid" ]] && ! pid_alive "$backend_pid"; then
        if wait "$backend_pid"; then
            status=0
        else
            status=$?
        fi
        printf 'Backend exited with status %s.\n' "$status" >&2
        exit "$status"
    fi

    if [[ -n "$frontend_pid" ]] && ! pid_alive "$frontend_pid"; then
        if wait "$frontend_pid"; then
            status=0
        else
            status=$?
        fi
        printf 'Frontend exited with status %s.\n' "$status" >&2
        exit "$status"
    fi
    sleep 1
done
