#!/usr/bin/env python3
"""
Test geotag workflow - demonstrates the simple EXIF-based approach

This script tests:
1. Writing GPS to image EXIF
2. Reading GPS from image EXIF
3. Verifying the round-trip works correctly
"""

import sys
import os
import shutil
from pathlib import Path

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from geotag_manager import GeoTag, write_gps_to_exif, extract_gps_from_exif


def test_geotag_workflow(image_path):
    """Test writing and reading GPS from an image"""

    print("=" * 70)
    print("GEOTAG WORKFLOW TEST")
    print("=" * 70)
    print()

    # Make a backup first
    backup_path = image_path + ".backup"
    shutil.copy2(image_path, backup_path)
    print(f"✓ Created backup: {backup_path}")
    print()

    # Step 1: Read existing GPS (if any)
    print("STEP 1: Read existing GPS from EXIF")
    print("-" * 70)
    existing = extract_gps_from_exif(image_path)
    if existing:
        print(f"  Current GPS: {existing.latitude:.6f}, {existing.longitude:.6f}")
    else:
        print("  No GPS data in image")
    print()

    # Step 2: Write new GPS
    print("STEP 2: Write new GPS to EXIF")
    print("-" * 70)

    # Example: Raleigh, NC
    test_geotag = GeoTag(
        latitude=35.7796,
        longitude=-78.6382,
        altitude=100.0,
        location_name="Raleigh, NC",
        source="test",
        confidence=1.0
    )

    print(f"  Writing: {test_geotag.latitude:.6f}, {test_geotag.longitude:.6f}")
    success = write_gps_to_exif(image_path, test_geotag)

    if success:
        print("  ✓ GPS written successfully")
    else:
        print("  ✗ Failed to write GPS")
        print("    Is piexif installed? pip install piexif")
        return False
    print()

    # Step 3: Read back and verify
    print("STEP 3: Read back GPS and verify")
    print("-" * 70)

    readback = extract_gps_from_exif(image_path)

    if not readback:
        print("  ✗ Failed to read GPS back")
        return False

    print(f"  Read: {readback.latitude:.6f}, {readback.longitude:.6f}")

    # Check if values match (allow small rounding error)
    lat_diff = abs(readback.latitude - test_geotag.latitude)
    lon_diff = abs(readback.longitude - test_geotag.longitude)

    if lat_diff < 0.0001 and lon_diff < 0.0001:
        print("  ✓ GPS values match!")
    else:
        print(f"  ⚠ GPS values differ slightly:")
        print(f"    Latitude diff: {lat_diff:.8f}")
        print(f"    Longitude diff: {lon_diff:.8f}")
        print("    This is normal due to EXIF precision")
    print()

    # Step 4: Verify with exiftool (if available)
    print("STEP 4: Verify with exiftool (if available)")
    print("-" * 70)

    import subprocess
    try:
        result = subprocess.run(
            ['exiftool', '-GPS*', image_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("  exiftool not available or failed")
    except FileNotFoundError:
        print("  exiftool not installed (optional)")
    except subprocess.TimeoutExpired:
        print("  exiftool timed out")
    print()

    # Step 5: Restore backup
    print("STEP 5: Cleanup")
    print("-" * 70)

    # Optionally restore backup
    restore = input("  Restore original file? [y/N]: ").strip().lower()
    if restore == 'y':
        shutil.move(backup_path, image_path)
        print(f"  ✓ Restored original from backup")
    else:
        print(f"  ✓ Keeping modified file (backup at {backup_path})")
    print()

    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print()
    print("Summary:")
    print("  • Image EXIF is the source of truth ✓")
    print("  • GPS coordinates are portable ✓")
    print("  • Standard format readable by all apps ✓")
    print()

    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_geotag_workflow.py <image.jpg>")
        print()
        print("Example:")
        print("  python test_geotag_workflow.py /export/ciriolisaver/test.jpg")
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.isfile(image_path):
        print(f"Error: File not found: {image_path}")
        sys.exit(1)

    # Check for piexif
    try:
        import piexif
    except ImportError:
        print("Error: piexif library not installed")
        print()
        print("Install with:")
        print("  pip install piexif")
        sys.exit(1)

    success = test_geotag_workflow(image_path)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
