#!/bin/bash
# Creates a zip file for packaging in the Roku Developer Dashboard.

PACKAGE_NAME="thingino-roku-viewer"
BUILD_DIR="dist"
ZIP_FILE="$BUILD_DIR/$PACKAGE_NAME.zip"

echo "Creating package directory..."
mkdir -p $BUILD_DIR

echo "Zipping the app to $ZIP_FILE..."
# Go to parent directory to ensure the zip paths are correct
cd ..
zip -r "roku/$ZIP_FILE" roku -x "roku/.git*" "roku/*deploy.sh*" "roku/*package.sh*" "roku/*.pkg*" "roku/dist/*" "roku/.*"

echo ""
echo "Successfully created package at: roku/$ZIP_FILE"
echo "Next steps:"
echo "1. Log into your Roku device's web portal (http://<ROKU_IP>)"
echo "2. Navigate to the 'Packager' utility."
echo "3. Upload this zip file and sign it with your developer key."
