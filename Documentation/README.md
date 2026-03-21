# Audio Processing App - Documentation

This directory contains technical documentation for the Audio Processing App.

## 📚 Documentation Index

### System Documentation
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Complete system architecture overview
  - Request flow diagrams
  - Component details (Nginx, Docker, Django)
  - File path references
  - Common issues and solutions
  - Deployment architecture

### Deployment & Operations
- **[DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md)** - Step-by-step deployment procedures
  - Backend deployment (Git)
  - Frontend deployment (SCP + build)
  - Verification steps
  - Troubleshooting guide

### Implementation Guides
- **[Implementation_Guides/](./Implementation_Guides/)** - Feature-specific implementation details

## 🔍 Quick Links

### For Troubleshooting Production Issues:
1. Start with [ARCHITECTURE.md](./ARCHITECTURE.md) - See "Common Issues & Solutions" section
2. Check [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) - "Troubleshooting" section
3. Review logs:
   - Nginx: `/var/log/nginx/error.log`
   - Docker: `docker logs audioapp_backend`

### For Deploying Updates:
1. **Backend changes:** [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) - "Backend Deployment" section
2. **Frontend changes:** [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) - "Frontend Deployment" section

### For Understanding System Design:
1. [ARCHITECTURE.md](./ARCHITECTURE.md) - Full architecture overview
2. Architecture diagrams - Request flow and component relationships

## 🛠️ Maintenance

When making significant changes to the system:
1. Update [ARCHITECTURE.md](./ARCHITECTURE.md) if architecture changes
2. Update [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) if deployment process changes
3. Document lessons learned from production issues
4. Keep troubleshooting sections current with new issues/solutions

---

**Last Updated:** March 21, 2026
