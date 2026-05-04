# Setting Up Automated Server Monitoring

This guide will help you set up automated monitoring for your production server.

---

## 📋 Prerequisites

- SSH access to server (nickd@82.165.221.205)
- sudo privileges
- 15 minutes of time

---

## 🚀 Quick Setup (5 Steps)

### Step 1: Upload Health Check Script (2 min)

From your local machine:

```powershell
# Upload the health check script
scp scripts/health_check.sh nickd@82.165.221.205:/tmp/health_check.sh
```

### Step 2: Install on Server (3 min)

SSH into the server:

```bash
ssh nickd@82.165.221.205
```

Then run:

```bash
# Create scripts directory
sudo mkdir -p /opt/audioapp/scripts
sudo mkdir -p /opt/audioapp/logs

# Move script and set permissions
sudo mv /tmp/health_check.sh /opt/audioapp/scripts/
sudo chmod +x /opt/audioapp/scripts/health_check.sh

# Edit the script to add your email
sudo nano /opt/audioapp/scripts/health_check.sh
# Change: ALERT_EMAIL="your-email@example.com"
# Save: Ctrl+X, Y, Enter
```

### Step 3: Test the Script (2 min)

Run it manually to make sure it works:

```bash
sudo /opt/audioapp/scripts/health_check.sh

# Check the log
cat /opt/audioapp/logs/health_check.log
```

You should see:
```
[2026-05-04 10:30:00] ====== Starting Health Check ======
[2026-05-04 10:30:01] Checking Docker containers...
[2026-05-04 10:30:01]   ✓ audioapp_backend: Up 2 days
...
[2026-05-04 10:30:05] ====== Health Check Complete ======
```

### Step 4: Set Up Automated Running (3 min)

Add to cron to run every 6 hours:

```bash
# Edit crontab
sudo crontab -e

# Add this line at the bottom:
0 */6 * * * /opt/audioapp/scripts/health_check.sh

# Save and exit
```

This will run the script at:
- 12:00 AM
- 6:00 AM
- 12:00 PM
- 6:00 PM

### Step 5: Set Up Email Alerts (Optional - 5 min)

If you want email alerts, install mailutils:

```bash
sudo apt update
sudo apt install -y mailutils

# Test email
echo "Test email from audio server" | mail -s "Test" your-email@example.com
```

---

## 🔔 Set Up UptimeRobot (Free Monitoring)

### Why?
- Monitors your site 24/7 from outside
- Sends SMS/email if site goes down
- Free for up to 50 monitors
- No server installation needed

### Steps:

1. **Sign up:** Go to https://uptimerobot.com/signUp

2. **Add monitors:**
   - Click "Add New Monitor"
   - Monitor Type: HTTP(s)
   - Friendly Name: "Audio App Frontend"
   - URL: https://audio.precisepouchtrack.com/
   - Monitoring Interval: 5 minutes (free tier)
   - Click "Create Monitor"

3. **Add API monitor:**
   - Click "Add New Monitor" again
   - Friendly Name: "Audio App API"
   - URL: https://audio.precisepouchtrack.com/api/projects/
   - Click "Create Monitor"

4. **Set up alerts:**
   - Go to "My Settings" → "Alert Contacts"
   - Add your email
   - Optionally: Add SMS (requires verification)

Done! You'll now get alerts if your site goes down.

---

## 📊 Set Up Netdata (Real-time Monitoring Dashboard)

### Why?
- Beautiful real-time dashboard
- See CPU, RAM, disk, network in real-time
- Free and open source
- Detects anomalies automatically

### Installation (5 min):

```bash
# SSH into server
ssh nickd@82.165.221.205

# Install Netdata (one command)
sudo bash <(curl -Ss https://my-netdata.io/kickstart.sh)

# Answer 'Y' to prompts
```

### Access Dashboard:

Open in browser: http://82.165.221.205:19999

**Security Note:** This is accessible from anywhere. To restrict access:

```bash
# Edit config
sudo nano /etc/netdata/netdata.conf

# Find and change:
[web]
    bind to = 127.0.0.1

# Save and restart
sudo systemctl restart netdata

# Now only accessible via SSH tunnel:
ssh -L 19999:localhost:19999 nickd@82.165.221.205
# Then visit: http://localhost:19999
```

---

## 🎯 What You Get After Setup

### Automated Monitoring:
- ✅ Health check runs every 6 hours
- ✅ Alerts if containers go down
- ✅ Alerts if disk/memory >85%
- ✅ Alerts if SSL expires <7 days
- ✅ Logs saved to `/opt/audioapp/logs/health_check.log`

### External Monitoring (UptimeRobot):
- ✅ Email/SMS if site goes down
- ✅ Response time tracking
- ✅ Uptime percentage
- ✅ Status page (optional)

### Real-time Dashboard (Netdata):
- ✅ Live CPU/RAM/disk graphs
- ✅ Container resource usage
- ✅ Anomaly detection
- ✅ Performance insights

---

## 🔧 Troubleshooting

### Health check script not running?

Check cron:
```bash
sudo crontab -l
# Should show: 0 */6 * * * /opt/audioapp/scripts/health_check.sh
```

Check cron logs:
```bash
sudo grep CRON /var/log/syslog | tail -20
```

### Not receiving email alerts?

Test email:
```bash
echo "Test" | mail -s "Test" your-email@example.com
```

Check spam folder!

### Can't access Netdata?

Check if running:
```bash
sudo systemctl status netdata
```

Check firewall:
```bash
sudo ufw status
# If blocked, allow: sudo ufw allow 19999
```

---

## 📅 Weekly Manual Checks

Even with automation, you should still do quick manual checks:

### Monday Morning (10 min):

```bash
# SSH into server
ssh nickd@82.165.221.205

# Quick check
sudo docker ps
sudo df -h
cat /opt/audioapp/logs/health_check.log | tail -50

# Check for security updates
sudo apt update && sudo apt list --upgradable
```

---

## 💡 Pro Tips

1. **Set up a maintenance calendar reminder** on your phone for weekly checks

2. **Join the UptimeRobot status page** - you can share with users

3. **Review logs weekly** - look for patterns before they become problems

4. **Test your alerts** - make sure they actually reach you!

5. **Document incidents** - keep notes when things go wrong

---

## 📞 Quick Reference Commands

```bash
# Check health manually
sudo /opt/audioapp/scripts/health_check.sh

# View health log
tail -f /opt/audioapp/logs/health_check.log

# Check all containers
sudo docker ps

# Restart if needed
cd /opt/audioapp && sudo docker-compose -f docker-compose.production.yml restart

# Check for updates
sudo apt update && sudo apt list --upgradable
```

---

## ✅ Setup Checklist

- [ ] Health check script uploaded and tested
- [ ] Cron job configured (runs every 6 hours)
- [ ] Email alerts configured
- [ ] UptimeRobot account created and monitoring
- [ ] Netdata installed and accessible
- [ ] Weekly calendar reminder set
- [ ] Emergency contact info documented

**You're all set!** 🎉

Your server is now monitoring itself and will alert you if anything goes wrong.

---

## 🆘 Still Need Help?

- Check the main maintenance schedule: `SERVER_MAINTENANCE_SCHEDULE.md`
- Quick reference card: `MAINTENANCE_QUICK_REFERENCE.md`
- Review health check logs: `/opt/audioapp/logs/health_check.log`
