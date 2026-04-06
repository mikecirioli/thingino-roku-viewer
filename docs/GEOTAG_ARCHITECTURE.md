# Geotag System Architecture

## Design Philosophy

**The image file is the source of truth.**

Geotag coordinates (latitude, longitude, altitude) are always stored in the image's EXIF data. The database is used only for:
1. **Management metadata** (source, confidence, location_name)
2. **Temporal indexing** (for clustering photos by time)
3. **Pending suggestions** (from auto-inference, awaiting approval)

This approach ensures:
- ✅ **Portability**: Copy a photo anywhere, geotag goes with it
- ✅ **Standard**: All photo apps can read the GPS data
- ✅ **Simple**: One source of truth, no sync issues
- ✅ **Safe**: Database is optional, can be rebuilt anytime

## Data Flow

### Reading Geotags
```
1. Read GPS coordinates from image EXIF
2. (Optional) Fetch metadata from database (source, confidence, location_name)
3. Return merged result
```

### Writing Geotags
```
1. Write GPS coordinates to image EXIF (MUST succeed)
2. (Optional) Store metadata in database for tracking
```

## Database Schema

The SQLite database stores **management metadata only**:

### `photos` table
Indexes all photos with their timestamps for clustering.
- `id` - Primary key
- `filename` - Photo filename
- `file_hash` - SHA256 (to detect file changes)
- `last_modified` - Unix timestamp
- `exif_timestamp` - EXIF creation time (for clustering)

### `geotags` table
Stores metadata **about** geotags (not the geotag itself).
- `photo_id` - Foreign key to photos
- `latitude`, `longitude`, `altitude` - **Cached copy for querying** (EXIF is source)
- `location_name` - Reverse geocoded name ("Raleigh, NC")
- `source` - How was this geotag created?
  - `exif` - Already in photo when imported
  - `manual` - User set via web UI
  - `inferred` - Auto-generated from temporal clustering
  - `google_photos` - Imported from Google Photos
- `confidence` - 0.0-1.0 (for inferred locations)
- `updated_at`, `updated_by` - Audit trail

## API Workflow

### GET `/photo/<filename>/geotag`
Returns geotag for a photo.

**Flow:**
1. Read GPS from image EXIF (source of truth)
2. If database available, fetch metadata (source, confidence, location_name)
3. Return merged result

**Response:**
```json
{
  "filename": "IMG_1234.jpg",
  "geotag": {
    "latitude": 35.788508,
    "longitude": -78.873086,
    "source": "manual",
    "location_name": "Raleigh, NC",
    "confidence": 1.0
  }
}
```

### PUT `/photo/<filename>/geotag`
Sets geotag for a photo (manual edit).

**Flow:**
1. **Write GPS to image EXIF** (REQUIRED - fails if piexif not available)
2. If database available, store metadata
3. Return success

**Request:**
```json
{
  "latitude": 35.788508,
  "longitude": -78.873086,
  "location_name": "Raleigh, NC"
}
```

### POST `/photos/geotag/import-exif`
Indexes all photos in the library.

**Flow:**
1. Scan photo directory
2. For each photo:
   - Extract EXIF timestamp
   - Add to database (for clustering)
   - Check if GPS exists (report count)
3. Return summary

**Does NOT modify any files** - just indexes what's already there.

### POST `/photos/geotag/auto-infer`
Uses temporal clustering to suggest geotags.

**Flow:**
1. Get all photos with GPS (from EXIF)
2. Get all photos without GPS (from database index)
3. Cluster by time (default: 1 hour window)
4. For each cluster:
   - Calculate centroid of photos with GPS
   - Calculate confidence based on time/distance
   - If confidence >= 0.5, suggest for photos without GPS
5. Return suggestions (does NOT apply them automatically)

**Response:**
```json
{
  "inferences": [
    {
      "filename": "IMG_5678.jpg",
      "geotag": {
        "latitude": 35.788,
        "longitude": -78.873,
        "confidence": 0.85
      },
      "reason": "5 ref photos, 10min apart, 0.3km spread"
    }
  ]
}
```

### POST `/photos/geotag/batch-update`
Applies the same geotag to multiple photos.

**Flow:**
1. For each filename:
   - Write GPS to image EXIF
   - Store metadata in database
2. Return count of successes/failures

**Use cases:**
- Apply auto-inferred suggestions after review
- Batch-tag vacation photos
- Fix incorrect GPS data in bulk

## Temporal Clustering Algorithm

Groups photos by time, infers location from nearby photos with GPS.

**Parameters:**
- `time_window` - Max seconds between photos in same cluster (default: 3600 = 1 hour)
- `min_refs` - Minimum reference photos needed (default: 2)
- `min_confidence` - Minimum confidence to suggest (default: 0.5)

**Confidence Calculation:**
```python
confidence = (
    ref_score * 0.3 +      # More reference photos = higher confidence
    spread_score * 0.4 +   # Tighter geographic spread = higher confidence  
    time_score * 0.3       # Closer in time = higher confidence
)
```

**Confidence Thresholds:**
- **0.9-1.0**: Very high - probably correct
- **0.7-0.9**: High - likely correct
- **0.5-0.7**: Medium - review recommended
- **<0.5**: Low - not suggested

**Example scenarios:**

| Scenario | Refs | Spread | Time Gap | Confidence |
|----------|------|--------|----------|------------|
| Burst photos at landmark | 10 | 0.1 km | 2 min | 0.95 |
| Walking tour | 5 | 0.8 km | 20 min | 0.80 |
| Road trip | 3 | 5 km | 45 min | 0.65 |
| Day trip | 2 | 15 km | 2 hours | 0.40 (not suggested) |

## Database Rebuild

Since the image EXIF is the source of truth, the database can be rebuilt anytime:

```bash
# Delete database
rm /data/geotags/geotags.db

# Restart server (auto-creates new database)
docker restart thingino-roku-viewer-server

# Re-index all photos
curl -X POST http://localhost:8099/photos/geotag/import-exif
```

All GPS data is preserved in the image files. You only lose:
- Location names (can be re-geocoded)
- Source tracking (exif vs manual vs inferred)
- Audit trail (who/when updated)

## Dependencies

### Python Libraries
- **Pillow** - Read EXIF data
- **piexif** - Write EXIF data ⚠️ **Required for manual editing**
- **PyYAML** - Config file parsing

### Optional Libraries
- **requests** - Reverse geocoding APIs
- **geopy** - Distance calculations (using built-in haversine instead)

## Performance

### Photo Library Scan
- **1,434 photos**: ~2-3 minutes
- **Rate**: ~8-10 photos/second
- **Bottleneck**: EXIF parsing

### Geotag Query
- **From EXIF**: ~50ms per photo
- **Bulk query**: Use database index for fast filtering
- **Temporal clustering**: <1 second for 1,434 photos

### EXIF Write
- **Per photo**: ~100-200ms
- **Batch update**: Parallelizable
- **Safety**: Creates backup, writes to temp, then renames

## Security & Privacy

### Home Location Detection
Many photos without GPS are taken at home. The system can:
1. Detect home location (cluster with 20%+ of photos)
2. Offer "privacy mode" to exclude from screensaver
3. Redact GPS when sharing photos

### API Authentication
All geotag endpoints require authentication:
- Session cookie (web UI)
- HTTP Basic auth (Roku, API clients)
- LAN bypass (local network access)

## Testing

### Manual EXIF Write Test
```python
from geotag_manager import GeoTag, write_gps_to_exif

geotag = GeoTag(latitude=35.788, longitude=-78.873)
success = write_gps_to_exif('/path/to/photo.jpg', geotag)

# Verify
from geotag_manager import extract_gps_from_exif
result = extract_gps_from_exif('/path/to/photo.jpg')
print(f"Wrote: {geotag.latitude}, {geotag.longitude}")
print(f"Read: {result.latitude}, {result.longitude}")
```

### API Test
```bash
# Set geotag
curl -X PUT http://localhost:8099/photo/test.jpg/geotag \
  -H "Content-Type: application/json" \
  -d '{"latitude": 35.788, "longitude": -78.873}'

# Read back
curl http://localhost:8099/photo/test.jpg/geotag

# Verify with exiftool
exiftool -GPS* test.jpg
```

## Future Enhancements

### Phase 1 (Current)
- ✅ EXIF read/write
- ✅ Temporal clustering
- ✅ Confidence scoring
- ✅ Basic API

### Phase 2 (Next)
- [ ] Web UI for editing
- [ ] Interactive map (Leaflet.js)
- [ ] Reverse geocoding (location names)
- [ ] Batch approval workflow

### Phase 3 (Later)
- [ ] Roku map overlay
- [ ] Filename pattern detection
- [ ] Google Photos API integration
- [ ] ML landmark detection

## Troubleshooting

### "Failed to write GPS to image EXIF"
**Cause**: `piexif` library not installed

**Fix**:
```bash
pip install piexif
# Or in Docker
docker exec -it container pip install piexif
```

### "Geotag database not available"
**Cause**: Database directory not writable

**Fix**:
```bash
mkdir -p /data/geotags
chmod 755 /data/geotags
```

### Auto-inference returns no suggestions
**Possible reasons**:
1. Photos don't have timestamps
2. No time clusters with mixed GPS coverage
3. Time window too narrow

**Try**:
```bash
# Increase time window to 2 hours
curl -X POST http://localhost:8099/photos/geotag/auto-infer \
  -d '{"time_window": 7200}'
```

### Coordinates written but not visible in photo viewer
**Cause**: Photo viewer caching old EXIF

**Fix**: Rename or touch the file to update mtime
```bash
touch photo.jpg
```
