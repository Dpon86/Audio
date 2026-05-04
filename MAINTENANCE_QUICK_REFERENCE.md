# Quick Reference: Production Server Maintenance
**Audio Processing Server - audio.precisepouchtrack.com**

---

## 🔴 DAILY (5 min - Automated Recommended)

```bash
# Quick health check (run this every morning)
ssh nickd@82.165.221.205 "sudo docker ps | grep audioapp && df -h | grep -E '(Filesystem|/)' && free -h"
```

**Look for:**
- ✅ All 5 containers "Up"
- ✅ Disk usage <80%
- ✅ Memory <85%

---

## 🟡 WEEKLY (45 min - Every Monday)

### 1. Security Updates (15 min)
```bash
ssh nickd@82.165.221.205 "sudo apt update && sudo apt list --upgradable"
```
**Action:** Apply security patches within 48 hours

### 2. Database Maintenance (10 min)
```bash
ssh nickd@82.165.221.205 "sudo docker exec audioapp_db psql -U audioapp_user -d audioapp_db -c 'VACUUM ANALYZE;'"
```

### 3. Error Log Check (10 min)
```bash
ssh nickd@82.165.221.205 "sudo docker logs --since 7d audioapp_backend 2>&1 | grep -i error | tail -20"
```

### 4. SSL Certificate Check (2 min)
```bash
echo | openssl s_client -servername audio.precisepouchtrack.com -connect audio.precisepouchtrack.com:443 2>/dev/null | openssl x509 -noout -dates
```
**Alert if:** <30 days until expiry

### 5. Disk Cleanup (8 min)
```bash
# Check log sizes
ssh nickd@82.165.221.205 "sudo du -sh /var/lib/docker/containers/*/*.log | sort -h | tail -5"

# Check media size
ssh nickd@82.165.221.205 "du -sh /opt/audioapp/backend/media/*"
```

---

## 🟠 MONTHLY (2 hours - First Sunday 2AM)

### 1. OS Updates (30 min)
```bash
ssh nickd@82.165.221.205 "sudo apt update && sudo apt upgrade -y && sudo reboot"
```

### 2. Backup Test (20 min)
```bash
ssh nickd@82.165.221.205 "sudo docker exec audioapp_db pg_dump -U audioapp_user -d audioapp_db -F c -f /tmp/backup_$(date +%Y%m%d).dump && ls -lh /tmp/backup_*.dump"
```

### 3. Performance Review (30 min)
- Review slow queries
- Check API response times
- Monitor user activity

---

## 🚨 EMERGENCY RESTART

### If site is down:

**Step 1:** Check status
```bash
ssh nickd@82.165.221.205 "sudo docker ps -a"
```

**Step 2:** Restart services
```bash
ssh nickd@82.165.221.205 "cd /opt/audioapp && sudo docker-compose -f docker-compose.production.yml restart"
```

**Step 3:** Check logs
```bash
ssh nickd@82.165.221.205 "sudo docker logs --tail 100 audioapp_backend"
```

**Nuclear Option:**
```bash
ssh nickd@82.165.221.205 "cd /opt/audioapp && sudo docker-compose -f docker-compose.production.yml down && sudo docker-compose -f docker-compose.production.yml up -d"
```

---

## 📊 Setup Automated Monitoring (One-time)

### UptimeRobot (Free)
1. Go to https://uptimerobot.com/
2. Add monitors for:
   - https://audio.precisepouchtrack.com/
   - https://audio.precisepouchtrack.com/api/projects/
3. Set alert email

### Netdata (Free - Real-time monitoring)
```bash
ssh nickd@82.165.221.205 "bash <(curl -Ss https://my-netdata.io/kickstart.sh)"
```
Access: http://82.165.221.205:19999

---

## 📅 MAINTENANCE CALENDAR

| Day | Task | Time |
|-----|------|------|
| **Every 6h** | Automated health check | 2 min |
| **Every Mon** | Weekly maintenance | 45 min |
| **1st Sun 2AM** | Monthly updates | 2 hours |
| **Quarterly** | Major updates & audit | Half day |

---

## ⚠️ ALERT THRESHOLDS

| Metric | Warning | Critical |
|--------|---------|----------|
| Disk Usage | >75% | >85% |
| Memory | >80% | >90% |
| SSL Expiry | <30 days | <7 days |
| Container Down | Any | Any |
| API Response | 5xx errors | No response |

---

## 📞 QUICK CONTACTS

- **Server IP:** 82.165.221.205
- **SSH User:** nickd
- **Database:** audioapp_db
- **DB User:** audioapp_user

---

## 🎯 MOST IMPORTANT

**The Big 3:**
1. ✅ **Daily:** Check all containers are up
2. ✅ **Weekly:** Apply security updates
3. ✅ **Monthly:** Test database backups

**Print this page and keep it handy!**
