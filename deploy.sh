#!/bin/bash
# Deploy script for the Hetzner production server. Run from the repo root,
# as the `deploy` user, on the application host.
set -e

cd "$(dirname "$0")"

echo "→ Pulling latest code…"
git pull origin main

echo "→ Installing Python dependencies…"
source venv/bin/activate
pip install -r requirements.txt

echo "→ Building frontend…"
cd frontend
npm install --no-audit --no-fund
npm run build
rm -rf ../app/static
mkdir -p ../app/static
cp -r dist/* ../app/static/
cd ..

echo "→ Running database migrations…"
alembic upgrade head

echo "→ Restarting service…"
sudo systemctl restart media-monitor
sudo systemctl status media-monitor --no-pager | head -10

echo "✓ Done. Visit https://mm.schenz.eu"
