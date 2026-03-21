#!/bin/bash
# AI Feature Deployment Script
# Run this on the server: sudo bash scripts/deploy_ai_feature.sh

set -e  # Exit on error

echo "=========================================="
echo "  AI Duplicate Detection - Deployment"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERROR: Please run with sudo${NC}"
    echo "sudo bash scripts/deploy_ai_feature.sh"
    exit 1
fi

echo -e "${YELLOW}Step 1: Navigate to app directory${NC}"
cd /opt/audioapp || { echo -e "${RED}ERROR: /opt/audioapp not found${NC}"; exit 1; }
pwd

echo ""
echo -e "${YELLOW}Step 2: Pull latest code from GitHub${NC}"
git pull origin master || { echo -e "${RED}ERROR: git pull failed${NC}"; exit 1; }
echo -e "${GREEN}✓ Code updated${NC}"

echo ""
echo -e "${YELLOW}Step 3: Update .env file with API key${NC}"
echo -e "${RED}⚠️  MANUAL STEP REQUIRED${NC}"
echo ""
echo "Please add your Anthropic API key to .env manually:"
echo "1. Edit .env: nano .env"
echo "2. Add these lines:"
echo ""
echo "   ANTHROPIC_API_KEY=<your-api-key-here>"
echo "   AI_PROVIDER=anthropic"
echo "   AI_MODEL=claude-3-5-sonnet-20241022"
echo "   AI_MAX_TOKENS=4096"
echo "   AI_COST_LIMIT_PER_USER_PER_MONTH=50.00"
echo ""
echo "3. Save and exit (Ctrl+X, Y, Enter)"
echo ""
read -p "Press Enter after you've added the API key..." 

echo ""
echo -e "${YELLOW}Step 4: Install new Python dependencies${NC}"
docker-compose exec audioapp pip install anthropic==0.39.0 || { echo -e "${RED}ERROR: Failed to install anthropic${NC}"; exit 1; }
echo -e "${GREEN}✓ Dependencies installed${NC}"

echo ""
echo -e "${YELLOW}Step 5: Generate database migrations${NC}"
docker-compose exec audioapp python manage.py makemigrations || { echo -e "${RED}ERROR: makemigrations failed${NC}"; exit 1; }
echo -e "${GREEN}✓ Migrations generated${NC}"

echo ""
echo -e "${YELLOW}Step 6: Apply database migrations${NC}"
docker-compose exec audioapp python manage.py migrate || { echo -e "${RED}ERROR: migrate failed${NC}"; exit 1; }
echo -e "${GREEN}✓ Database updated${NC}"

echo ""
echo -e "${YELLOW}Step 7: Restart Celery worker${NC}"
docker-compose restart audioapp_celery_worker || { echo -e "${RED}ERROR: Failed to restart Celery${NC}"; exit 1; }
echo -e "${GREEN}✓ Celery restarted${NC}"

echo ""
echo -e "${YELLOW}Step 8: Restart Django app${NC}"
docker-compose restart audioapp || { echo -e "${RED}ERROR: Failed to restart app${NC}"; exit 1; }
echo -e "${GREEN}✓ Django restarted${NC}"

echo ""
echo "=========================================="
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Verify API key: docker-compose exec audioapp python -c \"from django.conf import settings; print('API Key:', settings.ANTHROPIC_API_KEY[:20] + '...')\""
echo "2. Test AI client: docker-compose exec audioapp python manage.py shell"
echo "   >>> from audioDiagnostic.services.ai import AnthropicClient"
echo "   >>> client = AnthropicClient()"
echo "   >>> print('Client initialized successfully!')"
echo ""
echo "Cost monitoring:"
echo "- Monthly limit: \$50 per user"
echo "- Estimated: \$0.06 per hour of audio processed"
echo ""
