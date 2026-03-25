#!/bin/bash
# Creates a zip file for packaging in the Roku Developer Dashboard.

set -e

PACKAGE_NAME="3-bad-dogs"
BUILD_DIR="dist"
ZIP_FILE="$BUILD_DIR/$PACKAGE_NAME.zip"

echo "Creating package directory..."
mkdir -p $BUILD_DIR

# Change to the 'roku' directory to ensure correct zip paths
cd `dirname $0`

echo "Zipping the app to $ZIP_FILE..."
zip -r "$ZIP_FILE" . -x ".git*" "deploy.sh" "package.sh" "*.pkg" "dist/*" ".*" ".DS_Store" "*/.DS_Store"

echo ""
echo "Successfully created package at: $ZIP_FILE"
echo "Next steps:"
echo "1. Log into your Roku device's web portal (http://<ROKU_IP>)"
echo "2. Navigate to the 'Packager' utility."
echo "3. Upload this zip file and sign it with your developer key."
