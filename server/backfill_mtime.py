#!/usr/bin/env python3
"""Backfill file_mtime for existing photos"""

import os
import sys
from geotag_manager import GeotagDatabase

GEOTAG_DB_PATH = os.environ.get("GEOTAG_DB_PATH", "/data/geotags/geotags.db")
PHOTO_DIR = os.environ.get("PHOTO_DIR", "/media")

def main():
    print(f"Backfilling file_mtime for photos in {PHOTO_DIR}")
    db = GeotagDatabase(GEOTAG_DB_PATH)

    # Get all photos that have NULL file_mtime
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT id, filename FROM photos WHERE file_mtime IS NULL")
    photos = cursor.fetchall()

    print(f"Found {len(photos)} photos with NULL file_mtime")

    updated = 0
    for photo_id, filename in photos:
        photo_path = os.path.join(PHOTO_DIR, filename)
        if os.path.exists(photo_path):
            file_mtime = int(os.path.getmtime(photo_path))
            cursor.execute("UPDATE photos SET file_mtime = ? WHERE id = ?", (file_mtime, photo_id))
            updated += 1

    conn.commit()
    conn.close()

    print(f"Updated {updated} photos with file_mtime")

if __name__ == '__main__':
    main()
