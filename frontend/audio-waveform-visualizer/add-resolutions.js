const fs = require('fs');
const path = require('path');

// Read package.json
const packageJsonPath = path.join(__dirname, 'package.json');
const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));

// Add resolutions to use older css-minimizer-webpack-plugin
packageJson.resolutions = packageJson.resolutions || {};
packageJson.resolutions['css-minimizer-webpack-plugin'] = '3.4.1';

// Write back
fs.writeFileSync(packageJsonPath, JSON.stringify(packageJson, null, 2));
console.log('Added css-minimizer-webpack-plugin version resolution');
