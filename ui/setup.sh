#!/bin/bash
# MA3T UI Setup Script

echo "🚀 Setting up MA3T UI..."

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Update branding
echo "🎨 Updating branding..."
cp layout.tsx.new app/layout.tsx

# Start development server
echo "🏁 Starting development server..."
npm run dev