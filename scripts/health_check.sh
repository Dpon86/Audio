#!/bin/bash
#
# Audio Processing Server - Health Check Script
# Location: /opt/audioapp/scripts/health_check.sh
# Setup: chmod +x /opt/audioapp/scripts/health_check.sh
# Cron: 0 */6 * * * /opt/audioapp/scripts/health_check.sh
#

# Configuration
LOG_DIR="/opt/audioapp/logs"
LOG_FILE="$LOG_DIR/health_check.log"
ALERT_EMAIL="your-email@example.com"  # CHANGE THIS
WEBHOOK_URL=""  # Optional: Discord/Slack webhook

# Thresholds
DISK_WARNING=75
DISK_CRITICAL=85
MEMORY_WARNING=80
MEMORY_CRITICAL=90

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Function to send alert
send_alert() {
    local SEVERITY=$1
    local MESSAGE=$2
    
    log_message "[$SEVERITY] $MESSAGE"
    
    # Send email alert (requires mailutils installed)
    if [ -n "$ALERT_EMAIL" ] && command -v mail &> /dev/null; then
        echo "$MESSAGE" | mail -s "[$SEVERITY] Audio Server Alert" "$ALERT_EMAIL"
    fi
    
    # Send webhook alert
    if [ -n "$WEBHOOK_URL" ]; then
        curl -X POST "$WEBHOOK_URL" \
             -H "Content-Type: application/json" \
             -d "{\"content\": \"**[$SEVERITY]** $MESSAGE\"}" \
             &> /dev/null
    fi
}

# Start health check
log_message "====== Starting Health Check ======"

# 1. Check Docker containers
log_message "Checking Docker containers..."
CONTAINERS=("audioapp_backend" "audioapp_frontend" "audioapp_celery_worker" "audioapp_db" "audioapp_redis")
ALL_UP=true

for container in "${CONTAINERS[@]}"; do
    if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        send_alert "CRITICAL" "Container $container is not running!"
        ALL_UP=false
    else
        STATUS=$(docker ps --filter "name=$container" --format '{{.Status}}')
        log_message "  ✓ $container: $STATUS"
    fi
done

if [ "$ALL_UP" = true ]; then
    log_message "  ✓ All containers running"
fi

# 2. Check disk space
log_message "Checking disk space..."
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')

if [ "$DISK_USAGE" -gt "$DISK_CRITICAL" ]; then
    send_alert "CRITICAL" "Disk usage at ${DISK_USAGE}% (Critical threshold: ${DISK_CRITICAL}%)"
elif [ "$DISK_USAGE" -gt "$DISK_WARNING" ]; then
    send_alert "WARNING" "Disk usage at ${DISK_USAGE}% (Warning threshold: ${DISK_WARNING}%)"
else
    log_message "  ✓ Disk usage: ${DISK_USAGE}%"
fi

# 3. Check memory usage
log_message "Checking memory usage..."
MEMORY_USAGE=$(free | grep Mem | awk '{print int($3/$2 * 100)}')

if [ "$MEMORY_USAGE" -gt "$MEMORY_CRITICAL" ]; then
    send_alert "CRITICAL" "Memory usage at ${MEMORY_USAGE}% (Critical threshold: ${MEMORY_CRITICAL}%)"
elif [ "$MEMORY_USAGE" -gt "$MEMORY_WARNING" ]; then
    send_alert "WARNING" "Memory usage at ${MEMORY_USAGE}% (Warning threshold: ${MEMORY_WARNING}%)"
else
    log_message "  ✓ Memory usage: ${MEMORY_USAGE}%"
fi

# 4. Check API endpoint
log_message "Checking API endpoint..."
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://audio.precisepouchtrack.com/api/projects/ || echo "000")

if [ "$API_STATUS" != "200" ]; then
    send_alert "CRITICAL" "API not responding! Status code: $API_STATUS"
else
    log_message "  ✓ API responding (HTTP $API_STATUS)"
fi

# 5. Check frontend
log_message "Checking frontend..."
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://audio.precisepouchtrack.com/ || echo "000")

if [ "$FRONTEND_STATUS" != "200" ]; then
    send_alert "CRITICAL" "Frontend not responding! Status code: $FRONTEND_STATUS"
else
    log_message "  ✓ Frontend responding (HTTP $FRONTEND_STATUS)"
fi

# 6. Check SSL certificate expiry
log_message "Checking SSL certificate..."
CERT_EXPIRY=$(echo | openssl s_client -servername audio.precisepouchtrack.com -connect audio.precisepouchtrack.com:443 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
CERT_EXPIRY_EPOCH=$(date -d "$CERT_EXPIRY" +%s)
NOW_EPOCH=$(date +%s)
DAYS_UNTIL_EXPIRY=$(( ($CERT_EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))

if [ "$DAYS_UNTIL_EXPIRY" -lt 7 ]; then
    send_alert "CRITICAL" "SSL certificate expires in $DAYS_UNTIL_EXPIRY days!"
elif [ "$DAYS_UNTIL_EXPIRY" -lt 30 ]; then
    send_alert "WARNING" "SSL certificate expires in $DAYS_UNTIL_EXPIRY days"
else
    log_message "  ✓ SSL certificate valid for $DAYS_UNTIL_EXPIRY days"
fi

# 7. Check for errors in application logs (last hour)
log_message "Checking application logs..."
ERROR_COUNT=$(docker logs --since 1h audioapp_backend 2>&1 | grep -i "error" | grep -v "UserWarning" | wc -l)

if [ "$ERROR_COUNT" -gt 10 ]; then
    send_alert "WARNING" "Found $ERROR_COUNT errors in last hour in application logs"
elif [ "$ERROR_COUNT" -gt 0 ]; then
    log_message "  ⚠ Found $ERROR_COUNT errors in last hour (review recommended)"
else
    log_message "  ✓ No errors in last hour"
fi

# 8. Check database connectivity
log_message "Checking database connectivity..."
if docker exec audioapp_db psql -U audioapp_user -d audioapp_db -c "SELECT 1;" &> /dev/null; then
    log_message "  ✓ Database connection successful"
else
    send_alert "CRITICAL" "Cannot connect to database!"
fi

# 9. Check Redis connectivity
log_message "Checking Redis connectivity..."
if docker exec audioapp_redis redis-cli ping | grep -q "PONG"; then
    log_message "  ✓ Redis connection successful"
else
    send_alert "CRITICAL" "Cannot connect to Redis!"
fi

# Summary
log_message "====== Health Check Complete ======"
log_message ""

# Rotate log file if it gets too large (>10MB)
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null)
    if [ "$LOG_SIZE" -gt 10485760 ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        log_message "Log file rotated due to size"
    fi
fi

exit 0
