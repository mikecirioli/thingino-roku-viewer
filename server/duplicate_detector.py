#!/usr/bin/env python3
"""
Duplicate Photo Detector for 3 Bad Dogs Photo Frame

Uses perceptual hashing (pHash) to identify visually similar photos
regardless of resolution differences. Runs as a background daemon thread.

Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
"""

import os
import sqlite3
import json
import time
import threading
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime

try:
    import imagehash
    from PIL import Image
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    print("Warning: imagehash or PIL not available. Duplicate detection disabled.")


class DuplicateDetector:
    """
    Background daemon for detecting duplicate photos using perceptual hashing.

    Follows the same daemon pattern as TimelapseCapturer and ThumbnailGenerator.
    """

    def __init__(self, geotag_manager, photo_dir: str, interval: int = 300, batch_size: int = 50):
        """
        Initialize duplicate detector

        Args:
            geotag_manager: GeotagDatabase instance
            photo_dir: Directory containing photos
            interval: Seconds between processing runs (default 5 minutes)
            batch_size: Number of photos to process per run (default 50)
        """
        self._manager = geotag_manager
        self._photo_dir = photo_dir
        self._interval = interval
        self._batch_size = batch_size
        self._running = False
        self._thread = None
        self._hamming_threshold = 10  # Distance < 10 indicates duplicate

    def start(self):
        """Start the background daemon thread"""
        if not IMAGEHASH_AVAILABLE:
            print("  duplicates: imagehash not available, skipping")
            return

        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        print(f"  duplicates: detector started (interval={self._interval}s, batch_size={self._batch_size})")

    def stop(self):
        """Stop the background daemon thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _worker(self):
        """Main worker loop - runs in background thread"""
        # Initial delay before first run
        time.sleep(10)

        while self._running:
            try:
                self._process_batch()
            except Exception as e:
                print(f"  duplicates: error in processing batch: {e}")

            # Sleep for interval
            time.sleep(self._interval)

    def _process_batch(self):
        """
        Process a batch of photos:
        1. Find photos without pHash
        2. Calculate pHash for each
        3. Find and cluster duplicates
        """
        # Find photos needing pHash calculation
        photos_to_process = self._find_photos_without_phash()

        if not photos_to_process:
            # No new photos, check for new duplicates
            self._find_and_cluster_duplicates()
            return

        # Process batch
        processed = 0
        for photo_id, filename in photos_to_process[:self._batch_size]:
            try:
                photo_path = os.path.join(self._photo_dir, filename)
                if not os.path.exists(photo_path):
                    continue

                # Calculate pHash
                phash, width, height = self._calculate_phash(photo_path)
                if phash:
                    self._store_phash(photo_id, phash, width, height)
                    processed += 1
            except Exception as e:
                print(f"  duplicates: error processing {filename}: {e}")

        if processed > 0:
            print(f"  duplicates: calculated pHash for {processed} photos")
            # After processing new hashes, look for duplicates
            self._find_and_cluster_duplicates()

    def _find_photos_without_phash(self) -> List[Tuple[int, str]]:
        """Find photos that don't have pHash calculated yet"""
        conn = sqlite3.connect(self._manager.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT p.id, p.filename
            FROM photos p
            LEFT JOIN photo_hashes ph ON p.id = ph.photo_id
            WHERE ph.photo_id IS NULL
            LIMIT ?
        ''', (self._batch_size * 2,))  # Get extra in case some fail

        rows = cursor.fetchall()
        conn.close()

        return [(row['id'], row['filename']) for row in rows]

    def _calculate_phash(self, photo_path: str) -> Optional[Tuple[str, int, int]]:
        """
        Calculate perceptual hash for a photo

        Returns:
            Tuple of (phash_hex, width, height) or None if failed
        """
        try:
            img = Image.open(photo_path)
            width, height = img.size

            # Calculate pHash (returns ImageHash object)
            phash = imagehash.phash(img)

            # Convert to hex string
            phash_hex = str(phash)

            return (phash_hex, width, height)
        except Exception as e:
            print(f"  duplicates: error calculating phash for {photo_path}: {e}")
            return None

    def _store_phash(self, photo_id: int, phash: str, width: int, height: int):
        """Store calculated pHash in database"""
        megapixels = (width * height) / 1_000_000.0
        calculated_at = int(datetime.utcnow().timestamp())

        conn = sqlite3.connect(self._manager.db_path, timeout=30.0)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO photo_hashes
            (photo_id, phash, image_width, image_height, megapixels, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (photo_id, phash, width, height, megapixels, calculated_at))

        conn.commit()
        conn.close()

    def _find_and_cluster_duplicates(self):
        """
        Find all duplicate pairs using Hamming distance,
        then cluster into groups
        """
        # Get all pHashes
        conn = sqlite3.connect(self._manager.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT photo_id, phash
            FROM photo_hashes
        ''')

        rows = cursor.fetchall()
        conn.close()

        if len(rows) < 2:
            return  # Need at least 2 photos to find duplicates

        # Build list of (photo_id, phash_obj) tuples
        photos = []
        for row in rows:
            try:
                phash_obj = imagehash.hex_to_hash(row['phash'])
                photos.append((row['photo_id'], phash_obj))
            except:
                continue

        # Find all pairs with Hamming distance < threshold
        duplicate_pairs = []
        for i in range(len(photos)):
            for j in range(i + 1, len(photos)):
                photo_id_1, phash_1 = photos[i]
                photo_id_2, phash_2 = photos[j]

                # Calculate Hamming distance (convert to int for JSON serialization)
                distance = int(phash_1 - phash_2)

                if distance < self._hamming_threshold:
                    duplicate_pairs.append((photo_id_1, photo_id_2, distance))

        if not duplicate_pairs:
            return  # No duplicates found

        # Cluster pairs into groups
        groups = self._cluster_duplicates(duplicate_pairs)

        # Store duplicate groups
        for group_photo_ids, group_distances in groups:
            self._store_duplicate_group(group_photo_ids, group_distances)

        print(f"  duplicates: found {len(groups)} duplicate groups")

    def _cluster_duplicates(self, pairs: List[Tuple[int, int, int]]) -> List[Tuple[List[int], Dict[str, int]]]:
        """
        Cluster duplicate pairs into groups

        For example: (A,B), (B,C) → {A, B, C}

        Args:
            pairs: List of (photo_id_1, photo_id_2, distance) tuples

        Returns:
            List of (photo_ids, distances) where:
                photo_ids: list of photo IDs in group
                distances: dict mapping "id1-id2" to hamming distance
        """
        # Build adjacency graph
        graph = {}
        distances = {}

        for id1, id2, dist in pairs:
            if id1 not in graph:
                graph[id1] = set()
            if id2 not in graph:
                graph[id2] = set()
            graph[id1].add(id2)
            graph[id2].add(id1)

            # Store distance (use consistent ordering)
            key = f"{min(id1, id2)}-{max(id1, id2)}"
            distances[key] = dist

        # Find connected components (groups)
        visited = set()
        groups = []

        for node in graph:
            if node in visited:
                continue

            # BFS to find all connected nodes
            component = set()
            queue = [node]

            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)

                for neighbor in graph.get(current, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)

            # Extract distances for this group
            group_ids = sorted(list(component))
            group_distances = {}
            for i in range(len(group_ids)):
                for j in range(i + 1, len(group_ids)):
                    key = f"{group_ids[i]}-{group_ids[j]}"
                    if key in distances:
                        group_distances[key] = distances[key]

            groups.append((group_ids, group_distances))

        return groups

    def _store_duplicate_group(self, photo_ids: List[int], distances: Dict[str, int]):
        """Store a duplicate group in the database"""
        created_at = int(datetime.utcnow().timestamp())

        conn = sqlite3.connect(self._manager.db_path, timeout=30.0)
        cursor = conn.cursor()

        # Check if this exact group already exists (not reviewed yet)
        photo_ids_json = json.dumps(photo_ids)
        cursor.execute('''
            SELECT group_id FROM duplicate_groups
            WHERE photo_ids = ? AND reviewed_at IS NULL
        ''', (photo_ids_json,))

        existing = cursor.fetchone()
        if existing:
            conn.close()
            return  # Group already exists

        # Insert new group
        cursor.execute('''
            INSERT INTO duplicate_groups
            (photo_ids, hamming_distances, created_at, reviewed_at, kept_photo_id)
            VALUES (?, ?, ?, NULL, NULL)
        ''', (photo_ids_json, json.dumps(distances), created_at))

        conn.commit()
        conn.close()

    def get_unreviewed_groups(self) -> List[Dict]:
        """
        Get all unreviewed duplicate groups with photo details

        Returns:
            List of group dictionaries with photo details
        """
        conn = sqlite3.connect(self._manager.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT group_id, photo_ids, hamming_distances
            FROM duplicate_groups
            WHERE reviewed_at IS NULL
            ORDER BY group_id
        ''')

        groups = []
        for row in cursor.fetchall():
            group_id = row['group_id']
            photo_ids = json.loads(row['photo_ids'])
            distances = json.loads(row['hamming_distances'])

            # Get photo details
            photos = []
            for photo_id in photo_ids:
                cursor.execute('''
                    SELECT p.filename, ph.image_width, ph.image_height, ph.megapixels
                    FROM photos p
                    LEFT JOIN photo_hashes ph ON p.id = ph.photo_id
                    WHERE p.id = ?
                ''', (photo_id,))

                photo_row = cursor.fetchone()
                if photo_row:
                    # Get file size
                    photo_path = os.path.join(self._photo_dir, photo_row['filename'])
                    file_size = os.path.getsize(photo_path) if os.path.exists(photo_path) else 0

                    photos.append({
                        'photo_id': photo_id,
                        'filename': photo_row['filename'],
                        'resolution': f"{photo_row['image_width']}x{photo_row['image_height']}" if photo_row['image_width'] else "unknown",
                        'megapixels': round(photo_row['megapixels'], 2) if photo_row['megapixels'] else 0,
                        'file_size': file_size
                    })

            groups.append({
                'group_id': group_id,
                'photos': photos,
                'hamming_distances': distances
            })

        conn.close()
        return groups

    def resolve_duplicate_group(self, group_id: int, kept_photo_id: int, deleted_photo_ids: List[int]) -> bool:
        """
        Resolve a duplicate group by keeping one photo and deleting others

        Args:
            group_id: ID of duplicate group
            kept_photo_id: ID of photo to keep
            deleted_photo_ids: List of photo IDs to delete

        Returns:
            True if successful, False otherwise
        """
        conn = sqlite3.connect(self._manager.db_path, timeout=30.0)
        cursor = conn.cursor()

        try:
            # Mark group as reviewed
            reviewed_at = int(datetime.utcnow().timestamp())
            cursor.execute('''
                UPDATE duplicate_groups
                SET reviewed_at = ?, kept_photo_id = ?
                WHERE group_id = ?
            ''', (reviewed_at, kept_photo_id, group_id))

            # Delete photos (files + database records)
            for photo_id in deleted_photo_ids:
                # Get filename
                cursor.execute('SELECT filename FROM photos WHERE id = ?', (photo_id,))
                row = cursor.fetchone()
                if row:
                    filename = row[0]
                    photo_path = os.path.join(self._photo_dir, filename)

                    # Delete file
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                        print(f"  duplicates: deleted {filename}")

                    # Delete from database
                    cursor.execute('DELETE FROM photo_hashes WHERE photo_id = ?', (photo_id,))
                    cursor.execute('DELETE FROM geotags WHERE photo_id = ?', (photo_id,))
                    cursor.execute('DELETE FROM photos WHERE id = ?', (photo_id,))

            conn.commit()
            return True

        except Exception as e:
            print(f"  duplicates: error resolving group {group_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
