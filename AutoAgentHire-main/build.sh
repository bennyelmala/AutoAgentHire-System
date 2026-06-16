#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing Python dependencies..."
pip install --upgrade pip

# Use production requirements on cloud (excludes sentence-transformers/PyTorch = saves ~500MB RAM)
# This prevents OOM crashes on Render Standard (2GB) and smaller instances.
if [ -f "requirements-prod.txt" ]; then
    echo "Using requirements-prod.txt (cloud-optimized, no PyTorch)"
    pip install -r requirements-prod.txt
else
    pip install -r requirements.txt
fi

# Render does not allow root/sudo access, so we cannot run install-deps.
# Render's native environments usually already contain the required shared libraries for Chromium.
# playwright install-deps chromium

echo "Installing Playwright browsers..."
playwright install chromium

echo "Creating required directories..."
mkdir -p data/logs \
         data/resumes \
         data/job_listings \
         data/cover_letters \
         data/screenshots \
         data/reports \
         data/temp \
         data/templates \
         data/vectors \
         uploads/resumes

echo "Build complete!"
