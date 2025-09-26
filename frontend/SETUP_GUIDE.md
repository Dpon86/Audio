# Frontend Setup Guide

## Quick Start

### Prerequisites
- Node.js 16+ and npm 8+
- Backend Django server running on port 8000

### Installation

1. **Navigate to frontend directory:**
   ```bash
   cd frontend/audio-waveform-visualizer
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start development server:**
   ```bash 
   npm start
   ```

The app will open at `http://localhost:3000`

## Package Management

### Essential Commands

| Command | Description |
|---------|-------------|
| `npm install` | Install all dependencies |
| `npm start` | Start development server |
| `npm run build` | Create production build |
| `npm test` | Run test suite |
| `npm outdated` | Check for outdated packages |
| `npm audit` | Security vulnerability check |

### Dependency Categories

**Core Runtime Dependencies:**
- `react` & `react-dom` - React framework
- `react-router-dom` - Client-side routing  
- `react-scripts` - Build tools and dev server

**Testing Dependencies:**
- `@testing-library/*` packages - Testing utilities
- Built-in Jest testing framework

**Performance Monitoring:**
- `web-vitals` - Performance metrics

## Configuration Files

### package.json Templates

Three templates are provided:

1. **Current (Complete)**: `audio-waveform-visualizer/package.json`
   - Includes all current dependencies
   - Ready for development

2. **Template**: `package-template.json`
   - Enhanced with additional useful scripts
   - Includes engine requirements

3. **Minimal**: `package-minimal.json`
   - Only essential dependencies
   - For clean new setups

### Using Templates

To start fresh with minimal dependencies:
```bash
cp frontend/package-minimal.json frontend/audio-waveform-visualizer/package.json
cd frontend/audio-waveform-visualizer
npm install
```

## Development Workflow

### 1. Development Server
```bash
npm start
```
- Starts on `http://localhost:3000`
- Hot reloading enabled
- Proxies API calls to Django backend

### 2. Testing
```bash
npm test
```
- Runs in watch mode
- Automatically finds test files

### 3. Production Build
```bash
npm run build
```
- Creates optimized bundle in `build/` folder
- Ready for deployment

## Troubleshooting

### Common Issues

**Port 3000 already in use:**
```bash
PORT=3001 npm start
```

**Package installation fails:**
```bash
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

**Proxy not working:**
- Ensure Django server is running on port 8000
- Check proxy setting in package.json

**Node version issues:**
```bash
node --version  # Should be 16+
npm --version   # Should be 8+
```

### Clean Reinstall
```bash
# Remove all installed packages
rm -rf node_modules package-lock.json

# Clear npm cache
npm cache clean --force

# Reinstall everything
npm install
```

## Production Deployment

### Build for Production
```bash
npm run build
```

### Serve Static Files
```bash
# Install serve globally
npm install -g serve

# Serve the build folder
serve -s build
```

### Environment Variables

Create `.env` file in the root directory:
```bash
REACT_APP_API_URL=http://your-backend-url.com
REACT_APP_VERSION=$npm_package_version
```

Access in components:
```javascript
const apiUrl = process.env.REACT_APP_API_URL;
```

## Advanced Configuration

### Custom Webpack Config
To customize webpack without ejecting, use CRACO:
```bash
npm install @craco/craco
```

### Bundle Analysis
```bash
npm install --save-dev webpack-bundle-analyzer
npm run build
npx webpack-bundle-analyzer build/static/js/*.js
```

## Integration with Backend

### API Communication
The frontend communicates with Django backend via:
- Proxy configuration in package.json
- API endpoints defined in Django urls.py
- CORS handling (if needed for production)

### File Uploads
For audio file uploads, ensure:
- Django `DATA_UPLOAD_MAX_MEMORY_SIZE` is configured
- Frontend handles FormData for file uploads
- Progress tracking for large files