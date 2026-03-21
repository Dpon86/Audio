#!/usr/bin/env bash
set -u

COMPOSE_FILE="/opt/audioapp/docker-compose.production.yml"
APP_DIR="/opt/audioapp"
LOG_DIR="/opt/audioapp/logs"
PROJECT_LABEL="audioapp"

mkdir -p "$LOG_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

fail_count=0

get_container_id_by_service() {
  local service="$1"
  docker ps \
    --filter "label=com.docker.compose.project=${PROJECT_LABEL}" \
    --filter "label=com.docker.compose.service=${service}" \
    --format '{{.ID}}' | head -n1
}

check_service_running() {
  local service="$1"
  if [ -n "$(get_container_id_by_service "$service")" ]; then
    log "PASS: Service '$service' is running"
  else
    log "FAIL: Service '$service' is not running"
    fail_count=$((fail_count + 1))
  fi
}

check_service_healthy_if_available() {
  local service="$1"
  local container_id
  local health

  container_id="$(get_container_id_by_service "$service")"
  if [ -z "$container_id" ]; then
    log "FAIL: Service '$service' has no container id"
    fail_count=$((fail_count + 1))
    return
  fi

  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id" 2>/dev/null || echo unknown)"
  if [ "$health" = "none" ]; then
    log "INFO: Service '$service' has no healthcheck (skipped)"
  elif [ "$health" = "healthy" ]; then
    log "PASS: Service '$service' health is healthy"
  else
    log "FAIL: Service '$service' health is '$health'"
    fail_count=$((fail_count + 1))
  fi
}

wait_for_stack() {
  local timeout_seconds=180
  local waited=0

  log "Waiting up to ${timeout_seconds}s for stack to stabilize"
  while [ "$waited" -lt "$timeout_seconds" ]; do
    if [ -n "$(get_container_id_by_service "backend")" ] \
      && [ -n "$(get_container_id_by_service "celery_worker")" ] \
      && [ -n "$(get_container_id_by_service "db")" ] \
      && [ -n "$(get_container_id_by_service "redis")" ] \
      && [ -n "$(get_container_id_by_service "frontend")" ]; then
      log "Core services are running"
      return 0
    fi

    sleep 5
    waited=$((waited + 5))
  done

  log "FAIL: Services did not fully start in ${timeout_seconds}s"
  return 1
}

run_backend_checks() {
  local backend_container_id
  backend_container_id="$(get_container_id_by_service "backend")"

  if [ -z "$backend_container_id" ]; then
    log "FAIL: Backend container not found for backend checks"
    fail_count=$((fail_count + 1))
    return
  fi

  if docker exec "$backend_container_id" python manage.py check >/dev/null 2>&1; then
    log "PASS: Django check passed"
  else
    log "FAIL: Django check failed"
    fail_count=$((fail_count + 1))
  fi

  if docker exec "$backend_container_id" python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','myproject.settings'); django.setup(); from django.db import connection; connection.cursor().execute('SELECT 1')" >/dev/null 2>&1; then
    log "PASS: Backend database query succeeded"
  else
    log "FAIL: Backend database query failed"
    fail_count=$((fail_count + 1))
  fi

  if docker exec "$backend_container_id" python -c "import os, redis; r = redis.Redis(host=os.getenv('REDIS_HOST', 'redis'), port=int(os.getenv('REDIS_PORT', '6379'))); r.ping()" >/dev/null 2>&1; then
    log "PASS: Backend can reach Redis"
  else
    log "FAIL: Backend cannot reach Redis"
    fail_count=$((fail_count + 1))
  fi
}

run_celery_checks() {
  local celery_container_id
  celery_container_id="$(get_container_id_by_service "celery_worker")"

  if [ -z "$celery_container_id" ]; then
    log "FAIL: Celery worker container not found"
    fail_count=$((fail_count + 1))
    return
  fi

  if docker exec "$celery_container_id" celery -A myproject inspect ping --timeout=5 2>/dev/null | grep -q "pong"; then
    log "PASS: Celery inspect ping returned pong"
  else
    log "FAIL: Celery inspect ping failed"
    fail_count=$((fail_count + 1))
  fi
}

run_frontend_checks() {
  if ss -tln | grep -q ':3001 '; then
    log "PASS: Frontend port 3001 is listening"
  else
    log "FAIL: Frontend port 3001 is not listening"
    fail_count=$((fail_count + 1))
  fi

  if ss -tln | grep -q ':8001 '; then
    log "PASS: Backend port 8001 is listening"
  else
    log "FAIL: Backend port 8001 is not listening"
    fail_count=$((fail_count + 1))
  fi
}

main() {
  cd "$APP_DIR" || exit 1

  log "=== Post-reboot health check started ==="

  if ! wait_for_stack; then
    fail_count=$((fail_count + 1))
  fi

  check_service_running "db"
  check_service_running "redis"
  check_service_running "backend"
  check_service_running "celery_worker"
  check_service_running "frontend"

  check_service_healthy_if_available "db"
  check_service_healthy_if_available "redis"
  check_service_healthy_if_available "backend"
  check_service_healthy_if_available "celery_worker"
  check_service_healthy_if_available "frontend"

  run_backend_checks
  run_celery_checks
  run_frontend_checks

  if [ "$fail_count" -eq 0 ]; then
    log "RESULT: PASS (all checks succeeded)"
    log "=== Post-reboot health check finished ==="
    exit 0
  fi

  log "RESULT: FAIL (${fail_count} check(s) failed)"
  log "=== Post-reboot health check finished ==="
  exit 1
}

main
