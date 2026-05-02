#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: ./compile_map.sh <url_to_pbf>"
    echo "Example: ./compile_map.sh https://download.geofabrik.de/north-america/us/rhode-island-latest.osm.pbf"
    exit 1
fi

PBF_URL=$1
OUTPUT_NAME=$(basename $PBF_URL .osm.pbf)

echo "--- 1. Cleaning up old data ---"
rm -rf graph-cache

if [ ! -f map.osm.pbf ]; then
    echo "--- 2. Downloading OSM data: $OUTPUT_NAME ---"
    wget -q -N $PBF_URL -O map.osm.pbf
    echo "Download complete."
else
    echo "--- 2. Using existing OSM data: map.osm.pbf ---"
fi

echo "--- 3. Compiling GraphHopper Cache (This takes CPU/RAM) ---"
java -Xmx4g -jar graphhopper.jar import config.yml

echo "--- 4. Zipping for Android ---"
if [ -d "graph-cache" ]; then
    zip -r "${OUTPUT_NAME}.gh.zip" graph-cache
    echo "SUCCESS! Your file is ready: ${OUTPUT_NAME}.gh.zip"
    echo "Copy this file to your phone's storage to test."
else
    echo "ERROR: Compilation failed. Check the logs above."
fi
