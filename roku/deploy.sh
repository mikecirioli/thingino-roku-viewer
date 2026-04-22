#!/bin/bash
# Quick deploy script for Roku debugging
# Usage: ./deploy.sh <ROKU_IP> [PASSWORD]

# Change to the script's directory to ensure correct zip paths
cd "$(dirname "$0")" || exit

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
# Zip from the current directory (which is now the 'roku' directory)
zip -r $ZIP_FILE . -x "*.git*" "*deploy.sh*" "*.pkg*" "dist/*"

echo "2. Deploying to Roku ($ROKU_IP)..."
echo "   Uploading $(du -h $ZIP_FILE | cut -f1) package..."
RESPONSE=$(curl -v --max-time 60 -w "\nHTTP_STATUS:%{http_code}" --anyauth -u "rokudev:$DEV_PASSWORD" \
  -F "mysubmit=Install" \
  -F "archive=@$ZIP_FILE" \
  "http://$ROKU_IP/plugin_install" 2>&1)

HTTP_STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -e 's/.*HTTP_STATUS://')
BODY=$(echo "$RESPONSE" | sed -e 's/HTTP_STATUS\:.*//g')

rm -f $ZIP_FILE

if [ "$HTTP_STATUS" -eq 200 ]; then
  if echo "$BODY" | grep -q "Install Success"; then
    echo "Install Success"
  else
    echo "Install Failed. Raw output:"
    # Try to extract just the error message from the HTML
    echo "$BODY" | sed -n 's/.*<font color="#ff0000">\(.*\)<\/font>.*/\1/p' | sed 's/<br>/\n/g'
    exit 1
  fi
else
  echo "HTTP Error: $HTTP_STATUS"
  echo "Raw output:"
  echo "$BODY"
  exit 1
fi

echo "Deployment finished."
