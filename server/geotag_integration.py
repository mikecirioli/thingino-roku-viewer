#!/usr/bin/env python3
"""
Integration code for adding geotag endpoints to server.py

This file contains the code snippets to be added to server.py:
1. Import statements
2. Global geotag_db initialization
3. Endpoint handlers
4. do_PUT method

Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
"""

# ==============================================================================
# ADD TO IMPORTS (near top of server.py, after other imports)
# ==============================================================================
"""
from geotag_manager import (
    GeotagDatabase,
    GeoTag,
    extract_gps_from_exif,
    extract_exif_timestamp,
    cluster_photos_by_time,
    infer_geotags_from_cluster
)
"""

# ==============================================================================
# ADD AFTER LOADING CAMERAS (around line 100)
# ==============================================================================
"""
# Initialize geotag database
GEOTAG_DB_PATH = os.environ.get("GEOTAG_DB_PATH", "/data/geotags/geotags.db")
geotag_db = None

def init_geotag_db():
    global geotag_db
    try:
        geotag_db = GeotagDatabase(GEOTAG_DB_PATH)
        print(f"Geotag database initialized at {GEOTAG_DB_PATH}")
    except Exception as e:
        print(f"Warning: Failed to initialize geotag database: {e}")
        geotag_db = None

# Initialize on startup
init_geotag_db()
"""

# ==============================================================================
# ADD TO PhotoHandler.do_GET (in the elif chain, around line 1770)
# ==============================================================================
"""
        elif path == "/photos/geotags":
            self.serve_photos_geotags(parsed)
        elif path.startswith("/photo/") and path.endswith("/geotag"):
            self.serve_photo_geotag(path)
"""

# ==============================================================================
# ADD TO PhotoHandler.do_POST (in the elif chain, around line 1320)
# ==============================================================================
"""
        elif path == "/photos/geotag/import-exif":
            self.handle_geotag_import_exif()
        elif path == "/photos/geotag/auto-infer":
            self.handle_geotag_auto_infer()
        elif path == "/photos/geotag/batch-update":
            self.handle_geotag_batch_update()
"""

# ==============================================================================
# ADD NEW do_PUT METHOD TO PhotoHandler class (after do_POST)
# ==============================================================================
"""
    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Require authorization for all PUT requests
        if not self._is_request_authorized():
            self.send_error(401, "Authentication Required")
            return

        # --- Authorized PUT requests ---
        if path.startswith("/photo/") and path.endswith("/geotag"):
            self.handle_put_photo_geotag(path)
        else:
            self.send_error(404)
"""

# ==============================================================================
# ADD THESE METHOD IMPLEMENTATIONS TO PhotoHandler class (at end of class)
# ==============================================================================
"""
    def serve_photo_geotag(self, path):
        \"\"\"GET /photo/<filename>/geotag — get geotag for a photo\"\"\"
        if geotag_db is None:
            self.send_error(503, "Geotag database not available")
            return

        # Extract filename from path: /photo/IMG_1234.jpg/geotag
        parts = path.split('/')
        if len(parts) < 3:
            self.send_error(400, "Invalid path")
            return
        filename = parts[2]

        # Check if photo exists
        photo_path = os.path.join(PHOTO_DIR, filename)
        if not os.path.isfile(photo_path):
            self.send_error(404, "Photo not found")
            return

        # Try to get from database first
        geotag = geotag_db.get_geotag(filename)

        # Fallback to EXIF if not in database
        if geotag is None:
            geotag = extract_gps_from_exif(photo_path)

        response = {
            'filename': filename,
            'geotag': geotag.to_dict() if geotag else None
        }

        data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def handle_put_photo_geotag(self, path):
        \"\"\"PUT /photo/<filename>/geotag — set geotag for a photo\"\"\"
        if geotag_db is None:
            self.send_error(503, "Geotag database not available")
            return

        # Extract filename from path
        parts = path.split('/')
        if len(parts) < 3:
            self.send_error(400, "Invalid path")
            return
        filename = parts[2]

        # Check if photo exists
        photo_path = os.path.join(PHOTO_DIR, filename)
        if not os.path.isfile(photo_path):
            self.send_error(404, "Photo not found")
            return

        # Parse request body
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        # Validate required fields
        if 'latitude' not in data or 'longitude' not in data:
            self.send_error(400, "Missing latitude or longitude")
            return

        # Ensure photo is in database
        photo_id = geotag_db.get_photo_id(filename)
        if not photo_id:
            exif_ts = extract_exif_timestamp(photo_path)
            geotag_db.add_photo(filename, photo_path, exif_ts)

        # Create geotag
        geotag = GeoTag(
            latitude=float(data['latitude']),
            longitude=float(data['longitude']),
            altitude=float(data['altitude']) if 'altitude' in data else None,
            location_name=data.get('location_name'),
            source='manual',
            confidence=1.0,
            updated_by='user'
        )

        # Save to database
        success = geotag_db.set_geotag(filename, geotag)

        if success:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok'}).encode())
        else:
            self.send_error(500, "Failed to save geotag")

    def serve_photos_geotags(self, parsed):
        \"\"\"GET /photos/geotags?status=all|complete|missing — list photos with geotag status\"\"\"
        if geotag_db is None:
            self.send_error(503, "Geotag database not available")
            return

        params = parse_qs(parsed.query)
        status = params.get('status', ['all'])[0]

        if status not in ['all', 'complete', 'missing']:
            self.send_error(400, "Invalid status parameter")
            return

        photos = geotag_db.list_photos_by_status(status)

        data = json.dumps({'photos': photos}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def handle_geotag_import_exif(self):
        \"\"\"POST /photos/geotag/import-exif — import EXIF geotags for all photos\"\"\"
        if geotag_db is None:
            self.send_error(503, "Geotag database not available")
            return

        # Scan photo directory
        photos = get_photos()
        imported = 0
        skipped = 0
        errors = 0

        for photo_path in photos:
            try:
                filename = os.path.basename(photo_path)

                # Add photo to database if not exists
                photo_id = geotag_db.get_photo_id(filename)
                if not photo_id:
                    exif_ts = extract_exif_timestamp(photo_path)
                    geotag_db.add_photo(filename, photo_path, exif_ts)

                # Extract and save geotag
                geotag = extract_gps_from_exif(photo_path)
                if geotag:
                    geotag_db.set_geotag(filename, geotag)
                    imported += 1
                else:
                    skipped += 1

            except Exception as e:
                print(f"Error processing {photo_path}: {e}")
                errors += 1

        response = {
            'status': 'ok',
            'imported': imported,
            'skipped': skipped,
            'errors': errors
        }

        data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def handle_geotag_auto_infer(self):
        \"\"\"POST /photos/geotag/auto-infer — infer geotags using temporal clustering\"\"\"
        if geotag_db is None:
            self.send_error(503, "Geotag database not available")
            return

        # Parse request body for options
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            options = json.loads(body)
        except json.JSONDecodeError:
            options = {}

        time_window = options.get('time_window', 3600)  # 1 hour default

        # Get all photos with geotags
        photos_with_geotags = geotag_db.get_all_with_geotags()
        geotag_map = {filename: geotag for filename, _, geotag in photos_with_geotags}

        # Get photos without geotags
        photos_without = geotag_db.get_photos_without_geotags()

        # Cluster by time
        clusters = cluster_photos_by_time(photos_without, time_window)

        # Infer geotags for each cluster
        all_inferences = []
        for cluster in clusters:
            inferences = infer_geotags_from_cluster(cluster, geotag_map)
            all_inferences.extend(inferences)

        # Return suggestions (don't auto-apply)
        response = {
            'status': 'ok',
            'inferences': [
                {
                    'filename': inf['filename'],
                    'geotag': inf['geotag'].to_dict(),
                    'reason': inf['reason']
                }
                for inf in all_inferences
            ]
        }

        data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def handle_geotag_batch_update(self):
        \"\"\"POST /photos/geotag/batch-update — apply geotag to multiple photos\"\"\"
        if geotag_db is None:
            self.send_error(503, "Geotag database not available")
            return

        # Parse request body
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        # Validate required fields
        if 'filenames' not in data or 'geotag' not in data:
            self.send_error(400, "Missing filenames or geotag")
            return

        filenames = data['filenames']
        geotag_data = data['geotag']

        if 'latitude' not in geotag_data or 'longitude' not in geotag_data:
            self.send_error(400, "Missing latitude or longitude in geotag")
            return

        # Create geotag
        geotag = GeoTag(
            latitude=float(geotag_data['latitude']),
            longitude=float(geotag_data['longitude']),
            altitude=float(geotag_data['altitude']) if 'altitude' in geotag_data else None,
            location_name=geotag_data.get('location_name'),
            source=geotag_data.get('source', 'manual'),
            confidence=float(geotag_data.get('confidence', 1.0)),
            updated_by=geotag_data.get('updated_by', 'user')
        )

        # Apply to all photos
        success_count = 0
        error_count = 0

        for filename in filenames:
            photo_path = os.path.join(PHOTO_DIR, filename)
            if not os.path.isfile(photo_path):
                error_count += 1
                continue

            # Ensure photo is in database
            photo_id = geotag_db.get_photo_id(filename)
            if not photo_id:
                exif_ts = extract_exif_timestamp(photo_path)
                geotag_db.add_photo(filename, photo_path, exif_ts)

            # Save geotag
            if geotag_db.set_geotag(filename, geotag):
                success_count += 1
            else:
                error_count += 1

        response = {
            'status': 'ok',
            'updated': success_count,
            'errors': error_count
        }

        data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)
"""

print("Geotag integration code snippets ready")
print("See geotag_integration.py for details")
