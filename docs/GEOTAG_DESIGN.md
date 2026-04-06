# Geotag Management System Design

## Overview
System for storing, managing, and displaying geographic location data for photos in the 3 Bad Dogs photo frame.

## Current State (from audit)
- **1,434 total images** in `/export/ciriolisaver`
- **942 (65.7%)** have complete GPS EXIF data
- **479 (33.4%)** missing GPS data entirely
- **13 (0.9%)** have incomplete GPS metadata

## Storage Design

### Option 1: SQLite Database (RECOMMENDED)
**Pros:**
- Fast queries for location-based searches
- Easy to implement complex queries (find all photos in region, cluster by location)
- Transaction support
- No file proliferation
- Built into Python

**Cons:**
- Another dependency for clients
- Requires server API for all access

**Schema:**
```sql
CREATE TABLE photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    file_hash TEXT,  -- SHA256 to detect file changes
    last_modified INTEGER  -- Unix timestamp
);

CREATE TABLE geotags (
    photo_id INTEGER PRIMARY KEY,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    altitude REAL,
    location_name TEXT,  -- Reverse geocoded name
    source TEXT NOT NULL,  -- 'exif', 'manual', 'inferred', 'google_photos'
    confidence REAL,  -- 0.0-1.0 for inferred locations
    updated_at INTEGER NOT NULL,  -- Unix timestamp
    updated_by TEXT,  -- 'exif_import', 'user', 'auto_cluster'
    FOREIGN KEY (photo_id) REFERENCES photos(id)
);

CREATE INDEX idx_geotags_location ON geotags(latitude, longitude);
CREATE INDEX idx_photos_filename ON photos(filename);
```

### Option 2: JSON Sidecar Files
**Pros:**
- Simple, no database setup
- Easy to version control
- Portable

**Cons:**
- Slow for large datasets
- No transaction support
- File proliferation (1 JSON per image)

### Option 3: Single JSON Manifest
**Pros:**
- Simple
- Easy backup/restore
- Version control friendly

**Cons:**
- Must load entire file into memory
- Race conditions on concurrent updates
- Doesn't scale beyond ~10k photos

## Selected Approach: SQLite + Fallback to EXIF

**Primary:** SQLite database at `/data/geotags/geotags.db`

**Fallback:** Read directly from EXIF if no database entry (backward compatible)

**Write strategy:**
1. Import all existing EXIF data on first run
2. Manual edits go to database with `source='manual'` (overrides EXIF)
3. Auto-inferred locations with `confidence` score
4. Database entry always takes precedence over EXIF

## Data Model

```python
@dataclass
class GeoTag:
    latitude: float      # -90 to 90
    longitude: float     # -180 to 180
    altitude: float | None = None
    location_name: str | None = None  # "San Francisco, CA, USA"
    source: str = 'exif'  # exif|manual|inferred|google_photos
    confidence: float = 1.0  # 0.0-1.0
    updated_at: datetime
    updated_by: str | None = None
```

## Auto-Geotagging Strategies

### 1. Temporal Clustering (PRIORITY)
- Group photos by date/time within ±1 hour
- If 3+ photos in cluster have GPS, infer location for others
- Confidence based on:
  - Time delta (closer = higher confidence)
  - Number of reference points
  - Geographic spread of references

### 2. Google Photos API (if available)
- Check if user has Google Photos backup
- Use Google's location data if available
- Source: `google_photos`, confidence: 0.9

### 3. Reverse Image Search (LOW PRIORITY)
- Use Google Vision API or similar
- Identify landmarks
- Low confidence, manual review required

### 4. Manual Pattern Detection
- iPhone IMG_NNNN.jpg sequences often taken on same trip
- Facebook filenames with IDs from same event
- Batch apply location to entire sequence

## API Design

### GET `/photo/<filename>/geotag`
**Response:**
```json
{
  "filename": "IMG_1234.jpg",
  "geotag": {
    "latitude": 35.788508,
    "longitude": -78.873086,
    "altitude": 120.5,
    "location_name": "Raleigh, NC, USA",
    "source": "exif",
    "confidence": 1.0,
    "updated_at": "2026-04-06T10:30:00Z",
    "updated_by": "exif_import"
  }
}
```

### PUT `/photo/<filename>/geotag`
**Request:**
```json
{
  "latitude": 35.788508,
  "longitude": -78.873086,
  "location_name": "Custom location name"
}
```

### GET `/photos/geotags?status=missing|incomplete|complete`
**Response:**
```json
{
  "photos": [
    {
      "filename": "IMG_1234.jpg",
      "status": "complete",
      "geotag": { ... }
    },
    {
      "filename": "IMG_5678.jpg",
      "status": "missing",
      "geotag": null
    }
  ]
}
```

### POST `/photos/geotag/auto-infer`
**Request:**
```json
{
  "filenames": ["IMG_1234.jpg", "IMG_1235.jpg"],
  "strategy": "temporal_cluster"
}
```
**Response:**
```json
{
  "inferred": [
    {
      "filename": "IMG_1234.jpg",
      "geotag": { ... },
      "confidence": 0.85,
      "reason": "Clustered with 5 nearby photos within 30 minutes"
    }
  ],
  "failed": []
}
```

### POST `/photos/geotag/batch-update`
**Request:**
```json
{
  "filenames": ["IMG_1234.jpg", "IMG_1235.jpg"],
  "geotag": {
    "latitude": 35.788508,
    "longitude": -78.873086
  }
}
```

### GET `/photos/geotag/export`
Export all geotag data as JSON for backup/migration

## Roku Integration

### Server Side
**GET `/random` enhancement:**
```json
{
  "url": "/photo/IMG_1234.jpg",
  "geotag": {
    "latitude": 35.788508,
    "longitude": -78.873086,
    "location_name": "Raleigh, NC, USA"
  }
}
```

### Roku Client
- Static world map overlay (1920x1080 PNG with transparent oceans)
- Red pin placed at lat/lon coordinates
- Location name displayed below map
- Fade in/out with photo transitions

## Implementation Phases

### Phase 1: Database Setup (current)
- [x] Audit existing geotag data
- [ ] Create SQLite schema
- [ ] Import all existing EXIF data
- [ ] Add basic read API endpoints

### Phase 2: Web UI - Read-only
- [ ] Photo grid with geotag status badges
- [ ] Map view showing all geotagged photos (Leaflet.js)
- [ ] Click photo to see location on map
- [ ] Filter by: has geotag / missing geotag / incomplete

### Phase 3: Web UI - Editing
- [ ] Click on map to set location
- [ ] Manual lat/lon entry form
- [ ] Batch select photos for same location
- [ ] Reverse geocoding for location names

### Phase 4: Auto-geotagging
- [ ] Temporal clustering algorithm
- [ ] Auto-infer UI (show suggestions, approve/reject)
- [ ] Confidence scoring

### Phase 5: Roku Display
- [ ] Generate static world map overlay
- [ ] Add geotag display to ScreensaverScene
- [ ] Location name label

## Reverse Geocoding

Use free services:
- **Nominatim** (OpenStreetMap): https://nominatim.openstreetmap.org/reverse
  - Free, rate-limited (1 req/sec)
  - No API key required
- **BigDataCloud**: https://www.bigdatacloud.com/free-api
  - Free tier: 10k requests/month
  - No API key

Cache reverse geocoded names in database to avoid repeated API calls.

## Map Rendering

### For Web UI
Use **Leaflet.js** with OpenStreetMap tiles:
- Free, no API key
- Marker clustering for dense regions
- Click to edit location

### For Roku Overlay
Generate static map overlay:
1. Start with blank world map (equirectangular projection)
2. Calculate pixel position: `x = (lon + 180) * (width / 360)`
3. Calculate pixel position: `y = (90 - lat) * (height / 180)`
4. Draw red pin at (x, y)
5. Overlay on photo with 30% opacity

Alternative: Use Mapbox Static API (free tier: 50k requests/month)

## Security Considerations

- Geotag data can reveal home location - add privacy mode to exclude photos near home
- Store API keys securely (not in code)
- Rate limit auto-geocoding to avoid API abuse

## Future Enhancements

- Privacy zones (exclude photos within radius of home)
- Travel timeline view
- Heatmap of most photographed locations
- Export to KML for Google Earth
- Machine learning for landmark detection
