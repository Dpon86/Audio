#!/bin/bash

# Frontend Security Audit Script
# Run this script to check for security vulnerabilities in Node.js dependencies

echo "🔍 Running Frontend Security Audit..."
echo "=================================="

cd "$(dirname "$0")/audio-waveform-visualizer"

echo "📋 Current package versions:"
npm list --depth=0

echo ""
echo "🔒 Security audit:"
npm audit

echo ""
echo "📊 Audit summary:"
npm audit --audit-level=moderate

echo ""
echo "💡 To fix issues automatically, run:"
echo "   npm audit fix"
echo ""
echo "⚠️  For more severe issues that require manual review:"
echo "   npm audit fix --force"
echo ""
echo "📈 To check for outdated packages:"
echo "   npm outdated"