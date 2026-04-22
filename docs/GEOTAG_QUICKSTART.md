# Geotag Management - Quick Start Guide

## Overview

The geotag management system is now integrated into the 3 Bad Dogs server. GPS coordinates are stored **in the image EXIF** (portable!), with the database used only for management metadata.

## What's Been Completed

✅ **Phase 1: Foundation**
- Geotag audit tool (942/1434 photos have GPS data)
- EXIF read/write support (piexif library)
- Temporal clustering algorithm for auto-inference
- Complete server API implementation
- Database for metadata tracking (source, confidence, location names)

## Core Design

**Image EXIF = Source of Truth**
- GPS coordinates stored in image file (portable)
- Database stores management metadata only
- All reads come from EXIF
- All writes go to EXIF first

## API Endpoints

### GET `/photo/<filename>/geotag`
Get geotag for a specific photo (falls back to EXIF if not in database).

**Example:**
```bash
curl http://localhost:8099/photo/IMG_1234.jpg/geotag
```

**Response:**
```json
{
  "filename": "IMG_1234.jpg",
  "geotag": {
    "latitude": 35.788508,
    "longitude": -78.873086,
    "altitude": null,
    "location_name": null,
    "source": "exif",
    "confidence": 1.0,
    "updated_at": "2026-04-06T10:30:00Z",
    "updated_by": "exif_import"
  }
}
```

### PUT `/photo/<filename>/geotag`
Manually set geotag for a photo.

**Example:**
```bash
curl -X PUT http://localhost:8099/photo/IMG_1234.jpg/geotag \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 35.788508,
    "longitude": -78.873086,
    "location_name": "Raleigh, NC"
  }'
```

### GET `/photos/geotags?status=missing`
List photos by geotag status (`all`, `complete`, or `missing`).

**Example:**
```bash
curl http://localhost:8099/photos/geotags?status=missing
```

### POST `/photos/geotag/import-exif`
Index all photos with their timestamps (for temporal clustering).

**Does NOT modify files** - just indexes what's already there.

**Example:**
```bash
curl -X POST http://localhost:8099/photos/geotag/import-exif
```

**Response:**
```json
{
  "status": "ok",
  "indexed": 1434,
  "has_gps": 942,
  "missing_gps": 479,
  "errors": 0
}
```

### POST `/photos/geotag/auto-infer`
Use temporal clustering to suggest geotags for photos missing GPS data.

**Example:**
```bash
curl -X POST http://localhost:8099/photos/geotag/auto-infer \
  -H "Content-Type: application/json" \
  -d '{"time_window": 3600}'
```

**Response:**
```json
{
  "status": "ok",
  "inferences": [
    {
      "filename": "IMG_5678.jpg",
      "geotag": {
        "latitude": 35.788,
        "longitude": -78.873,
        "source": "inferred",
        "confidence": 0.85
      },
      "reason": "5 ref photos, 10min apart, 0.3km spread"
    }
  ]
}
```

### POST `/photos/geotag/batch-update`
Apply the same geotag to multiple photos.

**Example:**
```bash
curl -X POST http://localhost:8099/photos/geotag/batch-update \
  -H "Content-Type: application/json" \
  -d '{
    "filenames": ["IMG_1234.jpg", "IMG_1235.jpg", "IMG_1236.jpg"],
    "geotag": {
      "latitude": 35.788508,
      "longitude": -78.873086,
      "location_name": "Vacation trip"
    }
  }'
```

## Testing Locally

### 0. Install piexif (required for writing GPS)
```bash
pip install piexif
```

### 1. Test EXIF write on a single image
```bash
cd /export/git/3-bad-dogs/tools
python3 test_geotag_workflow.py /export/ciriolisaver/test.jpg
```

This will:
- Write GPS to the image EXIF
- Read it back and verify
- Offer to restore the original

### 2. Start the server
```bash
cd /export/git/3-bad-dogs/server
python3 server.py
```

You should see:
```
Geotag database initialized at /data/geotags/geotags.db
3-bad-dogs server: 1434 photos in /export/ciriolisaver, port 8099, refresh 30s
```

### 3. Index all photos
```bash
curl -X POST http://localhost:8099/photos/geotag/import-exif
```

This will scan all 1,434 photos and index their timestamps (for clustering).
**Does NOT modify files** - just indexes what's there.

### 4. Run auto-inference
```bash
curl -X POST http://localhost:8099/photos/geotag/auto-infer
```

This will analyze the 479 photos missing GPS and suggest locations based on temporal clustering.
**Does NOT apply them** - just returns suggestions for review.

### 5. Apply a suggestion (writes to EXIF!)
```bash
# Apply auto-inferred geotag to specific photos
curl -X POST http://localhost:8099/photos/geotag/batch-update \
  -H "Content-Type: application/json" \
  -d '{
    "filenames": ["IMG_5678.jpg"],
    "geotag": {
      "latitude": 35.788,
      "longitude": -78.873,
      "source": "inferred",
      "confidence": 0.85
    }
  }'
```

This **writes GPS to the image EXIF** - the geotag is now permanent.

### 6. Query missing photos
```bash
curl http://localhost:8099/photos/geotags?status=missing | jq
```

## Docker Deployment

The geotag database needs a persistent volume. Update your `docker-compose.yaml`:

```yaml
services:
  thingino-roku-viewer:
    build: .
    container_name: thingino-roku-viewer-server
    restart: unless-stopped
    ports:
      - "8099:8099"
    volumes:
      - ./config.yaml:/config/config.yaml:ro
      - /path/to/photos:/media:ro
      - ./timelapse:/data/timelapse              # existing
      - ./geotags:/data/geotags                  # NEW - geotag database
    environment:
      - GEOTAG_DB_PATH=/data/geotags/geotags.db
```

## What's Next

### Phase 2: Web UI (Complete)
The Geotags tab in the web UI now includes:
- Photo grid with GPS status badges (green/red)
- Interactive Leaflet.js map with photo pins
- Click to edit geotags
- Batch selection and editing tools
- Auto-inference review workflow

### Phase 3: Roku Display (Partial)
- Roku screensaver displays "City, Country, DD-MM-YYYY" via X-Photo-Info response header
- World map overlay with pin placement not yet implemented

## Files Created

- `server/geotag_manager.py` - Core geotag management classes
- `server/geotag_integration.py` - Integration documentation
- `tools/geotag_audit.py` - Photo library audit script
- `tools/geotag_audit_report.json` - Audit results
- `docs/GEOTAG_DESIGN.md` - System design document
- `docs/AUTO_GEOTAG_RESEARCH.md` - Auto-tagging research
- `docs/GEOTAG_QUICKSTART.md` - This file

## Database Schema

The SQLite database has two tables:

**photos**
- id (primary key)
- filename (unique)
- file_hash (SHA256)
- last_modified (Unix timestamp)
- exif_timestamp (Unix timestamp)

**geotags**
- photo_id (foreign key)
- latitude, longitude, altitude
- location_name
- source (exif|manual|inferred|google_photos)
- confidence (0.0-1.0)
- updated_at, updated_by

## Troubleshooting

### Database not initializing
Check that `/data/geotags/` directory exists and is writable:
```bash
mkdir -p /data/geotags
chmod 755 /data/geotags
```

### Photos not found
Verify `PHOTO_DIR` environment variable points to correct location:
```bash
echo $PHOTO_DIR
ls -la $PHOTO_DIR | head
```

### No inferences returned
This is normal if:
- Photos don't have timestamps
- No clusters of photos with and without GPS
- Time gaps are too large (>1 hour by default)

Try adjusting the time window:
```bash
curl -X POST http://localhost:8099/photos/geotag/auto-infer \
  -d '{"time_window": 7200}'  # 2 hours
```

## Performance Notes

- First EXIF import takes ~2-3 minutes for 1,434 photos
- Subsequent queries are instant (SQLite indexed)
- Auto-inference completes in <1 second
- Database file is ~100KB for 1,000 photos

## Next Steps

1. Test the API endpoints locally
2. Import your EXIF data
3. Run auto-inference to see suggested locations
4. Review design docs for web UI phase
5. Provide feedback on the inference quality

Once the web UI is complete, you'll be able to:
- Visually review and approve auto-inferred locations
- Click on a map to set locations
- Batch-apply locations to photo groups
- See which photos still need geotags

Then we'll add the map overlay to the Roku screensaver!
