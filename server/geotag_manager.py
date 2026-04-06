#!/usr/bin/env python3
"""
Geotag Management System for 3 Bad Dogs Photo Frame

Handles storage, retrieval, and inference of geographic location data for photos.
Uses SQLite for efficient storage and querying.

Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
"""

import os
import sqlite3
import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
import math

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


@dataclass
class GeoTag:
    """Geographic location data for a photo"""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    location_name: Optional[str] = None
    source: str = 'exif'  # exif|manual|inferred|google_photos
    confidence: float = 1.0
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime to ISO string if present
        if self.updated_at and isinstance(self.updated_at, datetime):
            data['updated_at'] = self.updated_at.isoformat() + 'Z'
        return data


class GeotagDatabase:
    """SQLite database for geotag storage and management"""

    def __init__(self, db_path: str):
        """
        Initialize geotag database

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Photos table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                file_hash TEXT,
                last_modified INTEGER,
                exif_timestamp INTEGER
            )
        ''')

        # Geotags table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS geotags (
                photo_id INTEGER PRIMARY KEY,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                altitude REAL,
                location_name TEXT,
                source TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                updated_at INTEGER NOT NULL,
                updated_by TEXT,
                FOREIGN KEY (photo_id) REFERENCES photos(id)
            )
        ''')

        # Indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_geotags_location
            ON geotags(latitude, longitude)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_photos_filename
            ON photos(filename)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_photos_timestamp
            ON photos(exif_timestamp)
        ''')

        conn.commit()
        conn.close()

    def _compute_file_hash(self, filepath: str) -> str:
        """Compute SHA256 hash of file for change detection"""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def add_photo(self, filename: str, filepath: str, exif_timestamp: Optional[int] = None):
        """
        Add or update photo record

        Args:
            filename: Photo filename (relative to photo directory)
            filepath: Full path to photo file
            exif_timestamp: EXIF timestamp (Unix seconds)
        """
        file_hash = self._compute_file_hash(filepath)
        last_modified = int(os.path.getmtime(filepath))

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO photos (filename, file_hash, last_modified, exif_timestamp)
            VALUES (?, ?, ?, ?)
        ''', (filename, file_hash, last_modified, exif_timestamp))

        conn.commit()
        photo_id = cursor.lastrowid
        conn.close()

        return photo_id

    def get_photo_id(self, filename: str) -> Optional[int]:
        """Get photo ID by filename"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM photos WHERE filename = ?', (filename,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def set_geotag_metadata(self, filename: str, geotag: GeoTag) -> bool:
        """
        Store geotag METADATA only (source, confidence, location_name)
        The actual geotag coordinates should be written to EXIF first!

        This database stores management metadata like:
        - source (manual, inferred, etc.)
        - confidence score
        - location_name (reverse geocoded)
        - who/when updated

        Args:
            filename: Photo filename
            geotag: GeoTag object

        Returns:
            True if successful, False otherwise
        """
        photo_id = self.get_photo_id(filename)
        if not photo_id:
            return False

        updated_at = int(datetime.utcnow().timestamp())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO geotags
            (photo_id, latitude, longitude, altitude, location_name,
             source, confidence, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (photo_id, geotag.latitude, geotag.longitude, geotag.altitude,
              geotag.location_name, geotag.source, geotag.confidence,
              updated_at, geotag.updated_by))

        conn.commit()
        conn.close()

        return True

    def get_geotag_metadata(self, filename: str) -> Optional[Dict]:
        """
        Get geotag METADATA for a photo (source, confidence, location_name)
        Does NOT return the actual coordinates - read those from EXIF!

        Args:
            filename: Photo filename

        Returns:
            Dict with metadata fields or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT source, confidence, location_name, updated_at, updated_by
            FROM geotags g
            JOIN photos p ON p.id = g.photo_id
            WHERE p.filename = ?
        ''', (filename,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            'source': row['source'],
            'confidence': row['confidence'],
            'location_name': row['location_name'],
            'updated_at': datetime.utcfromtimestamp(row['updated_at']).isoformat() + 'Z',
            'updated_by': row['updated_by']
        }

    def list_photos_by_status(self, status: str = 'all') -> List[Dict]:
        """
        List photos filtered by geotag status

        Args:
            status: 'all', 'complete', 'missing', or 'incomplete'

        Returns:
            List of photo dictionaries with geotag info
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if status == 'complete':
            query = '''
                SELECT p.filename, g.* FROM photos p
                JOIN geotags g ON p.id = g.photo_id
                WHERE g.latitude IS NOT NULL AND g.longitude IS NOT NULL
            '''
        elif status == 'missing':
            query = '''
                SELECT p.filename FROM photos p
                LEFT JOIN geotags g ON p.id = g.photo_id
                WHERE g.photo_id IS NULL
            '''
        else:  # all
            query = '''
                SELECT p.filename, g.* FROM photos p
                LEFT JOIN geotags g ON p.id = g.photo_id
            '''

        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            result = {'filename': row['filename']}
            if status != 'missing' and len(row.keys()) > 1:
                result['geotag'] = {
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                    'altitude': row['altitude'],
                    'location_name': row['location_name'],
                    'source': row['source'],
                    'confidence': row['confidence']
                }
            else:
                result['geotag'] = None

            results.append(result)

        return results

    def get_all_with_geotags(self) -> List[Tuple[str, GeoTag]]:
        """Get all photos that have geotags"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT p.filename, p.exif_timestamp, g.* FROM photos p
            JOIN geotags g ON p.id = g.photo_id
        ''')

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            geotag = GeoTag(
                latitude=row['latitude'],
                longitude=row['longitude'],
                altitude=row['altitude'],
                location_name=row['location_name'],
                source=row['source'],
                confidence=row['confidence'],
                updated_at=datetime.utcfromtimestamp(row['updated_at']).isoformat() + 'Z',
                updated_by=row['updated_by']
            )
            results.append((row['filename'], row['exif_timestamp'], geotag))

        return results

    def get_photos_without_geotags(self) -> List[Tuple[str, Optional[int]]]:
        """Get all photos that don't have geotags, with their timestamps"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT p.filename, p.exif_timestamp FROM photos p
            LEFT JOIN geotags g ON p.id = g.photo_id
            WHERE g.photo_id IS NULL
            ORDER BY p.exif_timestamp
        ''')

        rows = cursor.fetchall()
        conn.close()

        return rows


def extract_gps_from_exif(image_path: str) -> Optional[GeoTag]:
    """
    Extract GPS coordinates from image EXIF data

    Args:
        image_path: Path to image file

    Returns:
        GeoTag object or None if no GPS data
    """
    if not PILLOW_AVAILABLE:
        return None

    try:
        img = Image.open(image_path)
        exif = img.getexif()

        if not exif:
            return None

        gps_info = exif.get_ifd(0x8825)  # GPS IFD tag

        if not gps_info or len(gps_info) == 0:
            return None

        # Extract GPS data
        gps_data = {}
        for tag_id, value in gps_info.items():
            tag_name = GPSTAGS.get(tag_id, tag_id)
            gps_data[tag_name] = value

        # Check for required fields
        if 'GPSLatitude' not in gps_data or 'GPSLongitude' not in gps_data:
            return None

        # Convert to decimal degrees
        lat = _parse_gps_coordinate(
            gps_data.get('GPSLatitudeRef', 'N'),
            gps_data['GPSLatitude'][0],
            gps_data['GPSLatitude'][1],
            gps_data['GPSLatitude'][2]
        )

        lon = _parse_gps_coordinate(
            gps_data.get('GPSLongitudeRef', 'E'),
            gps_data['GPSLongitude'][0],
            gps_data['GPSLongitude'][1],
            gps_data['GPSLongitude'][2]
        )

        altitude = None
        if 'GPSAltitude' in gps_data:
            altitude = float(gps_data['GPSAltitude'])

        return GeoTag(
            latitude=lat,
            longitude=lon,
            altitude=altitude,
            source='exif',
            confidence=1.0,
            updated_at=datetime.utcnow().isoformat() + 'Z',
            updated_by='exif_import'
        )

    except Exception:
        return None


def extract_exif_timestamp(image_path: str) -> Optional[int]:
    """Extract EXIF creation timestamp from image"""
    if not PILLOW_AVAILABLE:
        return None

    try:
        img = Image.open(image_path)
        exif = img.getexif()

        if not exif:
            return None

        # Try DateTimeOriginal (36867) or DateTime (306)
        for tag_id in [36867, 306]:
            if tag_id in exif:
                dt_str = exif[tag_id]
                # Format: "2020:01:15 10:30:45"
                dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                return int(dt.timestamp())

        return None

    except Exception:
        return None


def write_gps_to_exif(image_path: str, geotag: GeoTag) -> bool:
    """
    Write GPS coordinates to image EXIF data

    Args:
        image_path: Path to image file
        geotag: GeoTag object with coordinates

    Returns:
        True if successful, False otherwise
    """
    if not PILLOW_AVAILABLE:
        return False

    try:
        import piexif
    except ImportError:
        print("Warning: piexif library not available. Install with: pip install piexif")
        return False

    try:
        # Read existing EXIF
        img = Image.open(image_path)

        try:
            exif_dict = piexif.load(image_path)
        except Exception:
            # No existing EXIF, create new
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        # Convert decimal degrees to degrees/minutes/seconds
        def _decimal_to_dms(decimal):
            """Convert decimal degrees to degrees, minutes, seconds tuple"""
            decimal = abs(decimal)
            degrees = int(decimal)
            minutes_decimal = (decimal - degrees) * 60
            minutes = int(minutes_decimal)
            seconds = (minutes_decimal - minutes) * 60
            # Store as rationals (piexif format)
            return ((degrees, 1), (minutes, 1), (int(seconds * 100), 100))

        # Build GPS IFD
        gps_ifd = {
            piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
            piexif.GPSIFD.GPSLatitudeRef: 'N' if geotag.latitude >= 0 else 'S',
            piexif.GPSIFD.GPSLatitude: _decimal_to_dms(geotag.latitude),
            piexif.GPSIFD.GPSLongitudeRef: 'E' if geotag.longitude >= 0 else 'W',
            piexif.GPSIFD.GPSLongitude: _decimal_to_dms(geotag.longitude),
        }

        # Add altitude if present
        if geotag.altitude is not None:
            gps_ifd[piexif.GPSIFD.GPSAltitude] = (int(abs(geotag.altitude) * 100), 100)
            gps_ifd[piexif.GPSIFD.GPSAltitudeRef] = 1 if geotag.altitude < 0 else 0

        exif_dict["GPS"] = gps_ifd

        # Convert to bytes
        exif_bytes = piexif.dump(exif_dict)

        # Save image with new EXIF
        img.save(image_path, exif=exif_bytes)

        return True

    except Exception as e:
        print(f"Error writing GPS to EXIF: {e}")
        return False


def _parse_gps_coordinate(ref: str, degrees, minutes, seconds) -> float:
    """Convert GPS coordinate from degrees/minutes/seconds to decimal"""
    decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    if ref in ['S', 'W']:
        decimal = -decimal
    return decimal


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points on Earth in kilometers

    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates

    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in kilometers

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def cluster_photos_by_time(photos_with_timestamps: List[Tuple[str, Optional[int]]],
                          time_window: int = 3600) -> List[List[Tuple[str, int]]]:
    """
    Cluster photos by timestamp

    Args:
        photos_with_timestamps: List of (filename, timestamp) tuples
        time_window: Maximum seconds between photos in same cluster (default: 1 hour)

    Returns:
        List of clusters, each containing photos taken within time_window
    """
    # Filter out photos without timestamps
    photos = [(f, t) for f, t in photos_with_timestamps if t is not None]

    if not photos:
        return []

    # Sort by timestamp
    photos.sort(key=lambda x: x[1])

    clusters = []
    current_cluster = [photos[0]]

    for filename, timestamp in photos[1:]:
        time_delta = timestamp - current_cluster[-1][1]

        if time_delta <= time_window:
            current_cluster.append((filename, timestamp))
        else:
            clusters.append(current_cluster)
            current_cluster = [(filename, timestamp)]

    if current_cluster:
        clusters.append(current_cluster)

    return clusters


def infer_geotags_from_cluster(cluster: List[Tuple[str, int]],
                               all_geotags: Dict[str, GeoTag],
                               min_refs: int = 2) -> List[Dict]:
    """
    Infer geotags for photos in a time cluster

    Args:
        cluster: List of (filename, timestamp) tuples
        all_geotags: Dict mapping filename to GeoTag for photos with GPS
        min_refs: Minimum number of reference photos needed

    Returns:
        List of inference suggestions with confidence scores
    """
    # Separate photos with and without GPS
    with_gps = [(f, t) for f, t in cluster if f in all_geotags]
    without_gps = [(f, t) for f, t in cluster if f not in all_geotags]

    if len(with_gps) < min_refs or len(without_gps) == 0:
        return []

    # Calculate centroid of reference photos
    avg_lat = sum(all_geotags[f].latitude for f, _ in with_gps) / len(with_gps)
    avg_lon = sum(all_geotags[f].longitude for f, _ in with_gps) / len(with_gps)

    # Calculate geographic spread (standard deviation)
    if len(with_gps) >= 2:
        distances = [
            haversine_distance(avg_lat, avg_lon, all_geotags[f].latitude, all_geotags[f].longitude)
            for f, _ in with_gps
        ]
        spread_km = sum(distances) / len(distances)
    else:
        spread_km = 0

    inferences = []
    for filename, timestamp in without_gps:
        # Find nearest reference photo by time
        time_deltas = [abs(timestamp - ref_ts) for _, ref_ts in with_gps]
        min_time_delta = min(time_deltas)

        # Calculate confidence
        confidence = _calculate_confidence(
            num_refs=len(with_gps),
            spread_km=spread_km,
            time_delta_sec=min_time_delta,
            cluster_size=len(cluster)
        )

        if confidence >= 0.5:  # Only suggest if >= 50% confidence
            inferences.append({
                'filename': filename,
                'geotag': GeoTag(
                    latitude=avg_lat,
                    longitude=avg_lon,
                    source='inferred',
                    confidence=confidence,
                    updated_at=datetime.utcnow().isoformat() + 'Z',
                    updated_by='temporal_cluster'
                ),
                'reason': f'{len(with_gps)} ref photos, {min_time_delta / 60:.0f}min apart, {spread_km:.1f}km spread'
            })

    return inferences


def _calculate_confidence(num_refs: int, spread_km: float,
                         time_delta_sec: int, cluster_size: int) -> float:
    """
    Calculate confidence score for inferred geotag

    Args:
        num_refs: Number of reference photos
        spread_km: Geographic spread of references
        time_delta_sec: Time to nearest reference
        cluster_size: Total cluster size

    Returns:
        Confidence score 0.0-1.0
    """
    # Reference point score: 0.5 for 2 refs, 1.0 for 5+
    ref_score = min(1.0, (num_refs - 1) / 4)

    # Spread score: 1.0 for <0.5km, 0.0 for >10km
    if spread_km < 0.5:
        spread_score = 1.0
    elif spread_km > 10:
        spread_score = 0.0
    else:
        spread_score = 1.0 - ((spread_km - 0.5) / 9.5)

    # Time score: 1.0 for <15min, 0.5 for 1hr, 0.0 for >2hr
    time_delta_min = time_delta_sec / 60
    if time_delta_min < 15:
        time_score = 1.0
    elif time_delta_min > 120:
        time_score = 0.0
    else:
        time_score = 1.0 - ((time_delta_min - 15) / 105)

    # Weighted average
    confidence = (ref_score * 0.3 + spread_score * 0.4 + time_score * 0.3)

    return round(confidence, 2)
