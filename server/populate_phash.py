#!/usr/bin/env python3
"""
One-time script to calculate pHash for all photos in the database.

Usage: python3 populate_phash.py
"""

import os
import sys
import time
from geotag_manager import GeotagDatabase
from duplicate_detector import DuplicateDetector

# Configuration (match server.py defaults)
GEOTAG_DB_PATH = os.environ.get("GEOTAG_DB_PATH", "/data/geotags/geotags.db")
PHOTO_DIR = os.environ.get("PHOTO_DIR", "/media")

def main():
    print(f"Initializing database: {GEOTAG_DB_PATH}")
    print(f"Photo directory: {PHOTO_DIR}")

    # Initialize
    geotag_db = GeotagDatabase(GEOTAG_DB_PATH)
    detector = DuplicateDetector(geotag_db, PHOTO_DIR, interval=300, batch_size=100)

    # Get total count
    photos_to_process = detector._find_photos_without_phash()
    total = len(photos_to_process)

    if total == 0:
        print("All photos already have pHash calculated!")
        return

    print(f"\nFound {total} photos without pHash")
    print(f"Starting processing...\n")

    processed = 0
    errors = 0
    start_time = time.time()

    for photo_id, filename in photos_to_process:
        try:
            photo_path = os.path.join(PHOTO_DIR, filename)
            if not os.path.exists(photo_path):
                print(f"  SKIP: {filename} (file not found)")
                continue

            # Calculate pHash and store
            result = detector._calculate_phash(photo_path)
            if result:
                phash, width, height = result
                detector._store_phash(photo_id, phash, width, height)
                processed += 1

                # Progress update every 50 photos
                if processed % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed
                    remaining = (total - processed) / rate if rate > 0 else 0
                    print(f"  Progress: {processed}/{total} ({processed*100//total}%) "
                          f"- {rate:.1f} photos/sec - ETA: {remaining:.0f}s")
            else:
                errors += 1

        except Exception as e:
            print(f"  ERROR: {filename}: {e}")
            errors += 1

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Completed in {elapsed:.1f} seconds")
    print(f"  Processed: {processed} photos")
    print(f"  Errors: {errors}")
    print(f"  Average: {processed/elapsed:.1f} photos/sec")

    # Now find and cluster duplicates
    print(f"\n{'='*60}")
    print("Searching for duplicates...")
    detector._find_and_cluster_duplicates()

    # Get count of duplicate groups
    groups = detector.get_unreviewed_groups()
    print(f"Found {len(groups)} duplicate groups")

    # Show summary
    if groups:
        print(f"\nDuplicate Summary:")
        for group in groups[:10]:  # Show first 10
            photo_names = [p['filename'] for p in group['photos']]
            print(f"  Group {group['group_id']}: {len(photo_names)} photos")
            for photo in group['photos']:
                print(f"    - {photo['filename']} ({photo['resolution']}, {photo['megapixels']} MP)")

        if len(groups) > 10:
            print(f"\n  ... and {len(groups) - 10} more groups")

if __name__ == '__main__':
    main()
