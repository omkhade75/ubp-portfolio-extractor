#!/usr/bin/env bash
set -o errexit

# Build React frontend
echo "Building React frontend..."
cd frontend
npm install
npm run build
cd ..

# Install Python backend dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Build complete."
