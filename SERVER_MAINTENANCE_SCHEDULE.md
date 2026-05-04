# Production Server Maintenance Schedule
**Server:** audio.precisepouchtrack.com (82.165.221.205)  
**Last Updated:** May 4, 2026

---

## 🔴 DAILY (Automated Monitoring Recommended)

### 1. System Health Check
**Time:** Every 6 hours (automated)
```bash
# Check all containers are running
ssh nickd@82.165.221.205 "sudo docker ps --filter 'name=audioapp' --format 'table {{.Names}}\t{{.Status}}'"

# Check disk space (alert if >80%)
ssh nickd@82.165.221.205 "df -h | grep -E '(Filesystem|/dev/sda|/dev/vda)'"

# Check memory usage
ssh nickd@82.165.221.205 "free -h"
```

**Alert if:**
- Any container is not "Up"
- Disk usage >80%
- Memory usage >85%

### 2. Application Health
**Time:** Every hour (automated)
```bash
# Check if API is responding
curl -I https://audio.precisepouchtrack.com/api/projects/

# Check frontend is serving
curl -I https://audio.precisepouchtrack.com/
```

**Alert if:** HTTP status ≠ 200

### 3. Error Log Review
**Time:** Once per day (morning)
```bash
# Check for critical errors in last 24 hours
ssh nickd@82.165.221.205 "sudo docker logs --since 24h audioapp_backend 2>&1 | grep -i 'error\|critical\|exception' | tail -50"
```

**Action:** Investigate any recurring errors

---

## 🟡 WEEKLY (Every Monday Morning)

### 1. Security Updates Check (15 min)
```bash
# Check for OS updates
ssh nickd@82.165.221.205 "sudo apt update && sudo apt list --upgradable"

# Check Docker version
ssh nickd@82.165.221.205 "docker --version"
```

**Action:** 
- Note security updates
- Schedule installation for low-traffic window
- **Apply security patches within 48 hours**

### 2. Database Health Check (10 min)
```bash
# Check database size and growth
ssh nickd@82.165.221.205 "sudo docker exec audioapp_db psql -U audioapp_user -d audioapp_db -c '\l+'"

# Check for bloat
ssh nickd@82.165.221.205 "sudo docker exec audioapp_db psql -U audioapp_user -d audioapp_db -c 'SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'\''.'\''||tablename)) AS size FROM pg_tables WHERE schemaname NOT IN ('\''pg_catalog'\'', '\''information_schema'\'') ORDER BY pg_total_relation_size(schemaname||'\''.'\''||tablename) DESC LIMIT 10;'"

# Vacuum analyze (maintenance)
ssh nickd@82.165.221.205 "sudo docker exec audioapp_db psql -U audioapp_user -d audioapp_db -c 'VACUUM ANALYZE;'"
```

**Review:**
- Database growth rate
- Largest tables
- Connection count

### 3. Backup Verification (10 min)
```bash
# Check backup volume exists and has recent data
ssh nickd@82.165.221.205 "sudo docker volume ls | grep postgres"
ssh nickd@82.165.221.205 "sudo ls -lh /var/lib/docker/volumes/audioapp_postgres_data/_data/ | tail"

# Test backup restoration (monthly - see below)
```

**Action:** Ensure automated backups are running

### 4. SSL Certificate Check (2 min)
```bash
# Check certificate expiry (should auto-renew with Let's Encrypt)
echo | openssl s_client -servername audio.precisepouchtrack.com -connect audio.precisepouchtrack.com:443 2>/dev/null | openssl x509 -noout -dates
```

**Alert if:** Certificate expires <30 days

### 5. Log Size Management (5 min)
```bash
# Check Docker log sizes
ssh nickd@82.165.221.205 "sudo du -sh /var/lib/docker/containers/*/*.log | sort -h | tail -10"

# Clean old logs if needed (rotate logs >100MB)
ssh nickd@82.165.221.205 "sudo truncate -s 0 /var/lib/docker/containers/[CONTAINER_ID]/[CONTAINER_ID]-json.log"
```

**Action:** Configure log rotation if logs exceed 500MB

### 6. Application Dependency Updates (5 min)
```bash
# Check Python package updates (security only)
ssh nickd@82.165.221.205 "sudo docker exec audioapp_backend pip list --outdated"

# Check for critical CVEs in dependencies
# Use: https://pypi.org/project/safety/
ssh nickd@82.165.221.205 "sudo docker exec audioapp_backend pip install safety && safety check"
```

**Action:** Note critical security updates for testing

---

## 🟠 MONTHLY (First Monday of Month)

### 1. Full Security Update (30 min)
```bash
# Apply OS updates (schedule maintenance window)
ssh nickd@82.165.221.205 "sudo apt update && sudo apt upgrade -y"
ssh nickd@82.165.221.205 "sudo reboot"

# Wait for reboot, verify all services restart
# Check all containers after reboot
```

**Best Time:** Sunday 2-4 AM (lowest traffic)

### 2. Database Backup Test (20 min)
```bash
# Create test backup
ssh nickd@82.165.221.205 "sudo docker exec audioapp_db pg_dump -U audioapp_user -d audioapp_db -F c -f /tmp/backup_test.dump"

# Download and verify backup size
ssh nickd@82.165.221.205 "ls -lh /tmp/backup_test.dump"

# Test restoration on separate test database (critical!)
```

**Action:** Store backup offsite (AWS S3, BackBlaze, etc.)

### 3. Performance Review (30 min)
```bash
# Review slow queries
ssh nickd@82.165.221.205 "sudo docker exec audioapp_db psql -U audioapp_user -d audioapp_db -c 'SELECT query, calls, total_time, mean_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;'"

# Check API response times
# Review Gunicorn worker performance
ssh nickd@82.165.221.205 "sudo docker logs audioapp_backend 2>&1 | grep 'worker'" 
```

**Action:** Optimize slow queries, adjust worker count if needed

### 4. Media Storage Cleanup (15 min)
```bash
# Check media folder size
ssh nickd@82.165.221.205 "sudo du -sh /opt/audioapp/backend/media/*"

# Find orphaned files (no database reference)
ssh nickd@82.165.221.205 "sudo docker exec audioapp_backend python manage.py cleanup_unused_media"
```

**Action:** Remove orphaned files to save space

### 5. User Activity Review (10 min)
```bash
# Check user growth and activity
ssh nickd@82.165.221.205 "sudo docker exec audioapp_backend python manage.py shell -c 'from accounts.models import User; print(f\"Total Users: {User.objects.count()}\"); print(f\"Active (last 30d): {User.objects.filter(last_login__gte=timezone.now()-timedelta(days=30)).count()}\")'"

# Review project count growth
```

**Action:** Monitor for unusual patterns

---

## 🔵 QUARTERLY (Every 3 Months)

### 1. Major Dependency Updates (2 hours)
**Test in development first!**
```bash
# Update Django (major versions require testing)
# Update DRF, Celery, PostgreSQL, Redis
# Update frontend dependencies (React, etc.)
```

**Process:**
1. Review release notes for breaking changes
2. Test in local/staging environment
3. Create database backup
4. Deploy during maintenance window
5. Monitor for 48 hours post-deployment

### 2. Security Audit (1 hour)
- Review user permissions
- Audit API endpoints
- Check for exposed sensitive data in logs
- Review firewall rules
- Scan for vulnerabilities: `nmap audio.precisepouchtrack.com`

### 3. Disaster Recovery Test (2 hours)
- Test complete backup restoration
- Verify backup automation
- Test failover procedures
- Document recovery time

### 4. Performance Optimization (2 hours)
- Database indexing review
- Query optimization
- CDN/caching evaluation
- Load testing

---

## 🟣 ANNUALLY (Once Per Year)

### 1. Infrastructure Review
- Evaluate server capacity vs. usage
- Consider scaling options
- Review hosting costs
- Evaluate new technologies

### 2. Full Security Penetration Test
- Hire external security audit (recommended)
- Test all attack vectors
- Update security policies

### 3. Compliance Review
- GDPR/data privacy compliance
- Terms of service update
- Privacy policy review
- User data export/deletion procedures

---

## 📊 Monitoring Tools (Recommended)

### Set Up Automated Monitoring:

1. **Uptime Monitoring** (Free tier available)
   - UptimeRobot: https://uptimerobot.com/
   - Monitor: frontend, API endpoints
   - Alert via email/SMS on downtime

2. **Server Monitoring** (Free/Paid)
   - Netdata: Real-time system monitoring
   ```bash
   ssh nickd@82.165.221.205 "bash <(curl -Ss https://my-netdata.io/kickstart.sh)"
   ```
   - Access: http://82.165.221.205:19999

3. **Application Performance Monitoring**
   - Sentry (free tier): Error tracking
   - Add to Django settings for exception capture

4. **Log Aggregation** (Optional)
   - Papertrail or Logtail: Centralized logging
   - Easier than SSH'ing for log review

---

## 🚨 Emergency Response

### If Server Goes Down:

1. **Check container status:**
   ```bash
   ssh nickd@82.165.221.205 "sudo docker ps -a"
   ```

2. **Restart containers:**
   ```bash
   ssh nickd@82.165.221.205 "cd /opt/audioapp && sudo docker-compose -f docker-compose.production.yml restart"
   ```

3. **Check logs:**
   ```bash
   ssh nickd@82.165.221.205 "sudo docker logs --tail 100 audioapp_backend"
   ```

4. **Nuclear option (if needed):**
   ```bash
   ssh nickd@82.165.221.205 "cd /opt/audioapp && sudo docker-compose -f docker-compose.production.yml down && sudo docker-compose -f docker-compose.production.yml up -d"
   ```

### Contact Info:
- Hosting Provider: [Your provider support]
- Database Admin: [Contact]
- Emergency On-Call: [Phone number]

---

## 📋 Maintenance Log Template

Keep a maintenance log at `/opt/audioapp/maintenance_log.md`:

```markdown
## [Date] - [Your Name]
**Type:** Daily/Weekly/Monthly/Emergency
**Duration:** X minutes
**Actions Taken:**
- Updated OS packages
- Restarted backend container
- etc.

**Issues Found:**
- None / [Description]

**Follow-up Required:**
- None / [Action items]
```

---

## 🎯 Priority Summary

| Frequency | Time Required | Critical? |
|-----------|---------------|-----------|
| Daily monitoring (automated) | 5 min | ✅ YES |
| Weekly checks | 45 min | ⚠️ Important |
| Monthly maintenance | 2 hours | ⚠️ Important |
| Quarterly updates | 4-6 hours | 📅 Scheduled |
| Annual review | 1 day | 📅 Scheduled |

---

## 💰 Budget Considerations

**Free Tools:**
- UptimeRobot (basic monitoring)
- Netdata (server monitoring)
- Let's Encrypt (SSL)
- Weekly manual checks

**Paid (Optional but Recommended):**
- Sentry ($26/mo) - Error tracking
- Automated backups ($5-20/mo) - Offsite storage
- Security scanning ($15/mo) - Vulnerability detection
- Load testing service (as needed)

**Total Monthly Cost:** $0-50 depending on scale

---

## 🔧 Automation Scripts

Create this file on server: `/opt/audioapp/scripts/health_check.sh`

```bash
#!/bin/bash
# Daily health check script
# Run with: cron (0 */6 * * * /opt/audioapp/scripts/health_check.sh)

LOG_FILE="/opt/audioapp/logs/health_check.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] Starting health check..." >> $LOG_FILE

# Check containers
if ! docker ps | grep -q "audioapp_backend.*Up"; then
    echo "[$DATE] ALERT: Backend container down!" >> $LOG_FILE
    # Send alert (email, webhook, etc.)
fi

# Check disk space
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "[$DATE] WARNING: Disk usage at ${DISK_USAGE}%" >> $LOG_FILE
fi

# Check API
if ! curl -s -o /dev/null -w "%{http_code}" https://audio.precisepouchtrack.com/api/projects/ | grep -q "200"; then
    echo "[$DATE] ALERT: API not responding!" >> $LOG_FILE
fi

echo "[$DATE] Health check complete" >> $LOG_FILE
```

---

## 📞 Need Help?

- Review logs: `sudo docker logs audioapp_backend --tail 100`
- Check this document's history for past issues
- Discord/community support channels
- Stack Overflow for specific errors

**Document Version:** 1.0  
**Next Review Date:** [3 months from now]
