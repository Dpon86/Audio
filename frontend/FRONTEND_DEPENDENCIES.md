# Frontend JavaScript Dependencies

This document details all the JavaScript/Node.js dependencies for the Audio Repetitive Detection frontend.

## Node.js Version Requirements

- **Node.js**: 16.x or higher
- **npm**: 8.x or higher (npm 11.6.1 available for upgrade)

## Core React Dependencies

### React Framework
```json
{
  "react": "^19.1.0",
  "react-dom": "^19.1.0"
}
```

- **react**: The core React library for building user interfaces
- **react-dom**: React package for working with the DOM

### Routing
```json
{
  "react-router-dom": "^7.6.0"
}
```

- **react-router-dom**: Declarative routing for React applications

### Build Tools
```json
{
  "react-scripts": "5.0.1"
}
```

- **react-scripts**: Scripts and configuration used by Create React App

## Testing Dependencies

```json
{
  "@testing-library/dom": "^10.4.0",
  "@testing-library/jest-dom": "^6.6.3", 
  "@testing-library/react": "^16.3.0",
  "@testing-library/user-event": "^13.5.0"
}
```

- **@testing-library/dom**: Simple and complete DOM testing utilities
- **@testing-library/jest-dom**: Custom Jest matchers for testing DOM nodes
- **@testing-library/react**: Simple and complete React DOM testing utilities
- **@testing-library/user-event**: Fire events the same way the user does

## Performance Monitoring

```json
{
  "web-vitals": "^2.1.4"
}
```

- **web-vitals**: Library for measuring all the Web Vitals metrics

## Project Configuration

### Proxy Configuration
The frontend is configured to proxy API requests to the Django backend:
```json
{
  "proxy": "http://127.0.0.1:8000"
}
```

### Browser Support
```json
{
  "browserslist": {
    "production": [
      ">0.2%",
      "not dead", 
      "not op_mini all"
    ],
    "development": [
      "last 1 chrome version",
      "last 1 firefox version", 
      "last 1 safari version"
    ]
  }
}
```

## Available Scripts

```json
{
  "scripts": {
    "start": "react-scripts start",    // Development server
    "build": "react-scripts build",   // Production build
    "test": "react-scripts test",     // Run tests
    "eject": "react-scripts eject"    // Eject from Create React App
  }
}
```

## Installation Instructions

### Installing Dependencies

Navigate to the frontend directory:
```bash
cd frontend/audio-waveform-visualizer
```

Install all dependencies:
```bash
npm install
```

### Development Server

Start the development server:
```bash
npm start
```

The application will open at `http://localhost:3000` and proxy API calls to `http://127.0.0.1:8000` (Django backend).

### Production Build

Create an optimized production build:
```bash
npm run build
```

The build folder will contain the optimized files ready for deployment.

### Testing

Run the test suite:
```bash
npm test
```

## Dependency Management

### Updating Dependencies

Check for outdated packages:
```bash
npm outdated
```

Update all dependencies:
```bash
npm update
```

Update specific package:
```bash
npm install react@latest
```

### Security Auditing

Check for security vulnerabilities:
```bash
npm audit
```

Fix security issues:
```bash
npm audit fix
```

## Development Dependencies vs Production Dependencies

All the packages in this project are listed under `dependencies` rather than `devDependencies` because they are needed for the application to run. In a typical React project:

- **dependencies**: Packages needed for the app to run
- **devDependencies**: Packages only needed during development

## Package Lock File

The `package-lock.json` file locks the versions of all dependencies and their sub-dependencies to ensure consistent installs across different environments. This file should be committed to version control.

## Troubleshooting

### Common Issues

1. **Node version conflicts**: Use nvm (Node Version Manager) to manage Node.js versions
2. **Package installation failures**: Clear npm cache with `npm cache clean --force`
3. **Port conflicts**: React dev server uses port 3000 by default, can be changed with `PORT=3001 npm start`
4. **Proxy issues**: Ensure Django backend is running on port 8000

### Clearing Cache

If you encounter issues, try clearing the npm cache:
```bash
npm cache clean --force
```

Remove node_modules and reinstall:
```bash
rm -rf node_modules package-lock.json
npm install
```