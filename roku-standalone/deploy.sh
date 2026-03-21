#!/bin/bash
# Quick deploy script for Roku debugging
# Usage: ./deploy.sh <ROKU_IP> [PASSWORD]

if [ -z "$1" ]; then
  echo "Usage: ./deploy.sh <ROKU_IP> [PASSWORD]"
  exit 1
fi

ROKU_IP=$1
DEV_PASSWORD=$2

if [ -z "$DEV_PASSWORD" ]; then
  read -s -p "Enter Roku Developer Password: " DEV_PASSWORD
  echo ""
fi
ZIP_FILE="/tmp/3-bad-dogs-dev.zip"

echo "1. Zipping the app..."
rm -f $ZIP_FILE
zip -r $ZIP_FILE . -x "*.git*" "*deploy.sh*" "*.pkg*"

echo "2. Deploying to Roku ($ROKU_IP)..."
RESPONSE=$(curl -sS -w "\nHTTP_STATUS:%{http_code}" --anyauth -u "rokudev:$DEV_PASSWORD" \
  -F "mysubmit=Install" \
  -F "archive=@$ZIP_FILE" \
  "http://$ROKU_IP/plugin_install")

HTTP_STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -e 's/.*HTTP_STATUS://')
BODY=$(echo "$RESPONSE" | sed -e 's/HTTP_STATUS\:.*//g')

if [ "$HTTP_STATUS" -eq 200 ]; then
  if echo "$BODY" | grep -q "Install Success"; then
    echo "Install Success"
  else
    echo "Install Failed. Raw output:"
    echo "$BODY" | grep -v 'div class' | grep -v 'style' | grep -i 'error\|compilation\|failure\|message' || echo "$BODY"
    exit 1
  fi
else
  echo "HTTP Error: $HTTP_STATUS"
  echo "Raw output:"
  echo "$BODY"
  exit 1
fi

echo "Deployment finished."
