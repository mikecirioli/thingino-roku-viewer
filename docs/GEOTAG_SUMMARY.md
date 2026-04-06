# Geotag Management System - Summary

## The Simple Approach

After your feedback, we simplified the design:

### Image EXIF = Source of Truth ✓

**GPS coordinates (lat/lon/altitude) are stored IN the image file's EXIF data.**

This means:
- ✅ Copy a photo → geotag goes with it (portable)
- ✅ Works with all photo apps (standard format)
- ✅ No database required for basic functionality
- ✅ Can't get "out of sync" (one source of truth)

### Database = Management Metadata Only

The SQLite database stores **extra metadata** for managing geotags:
- `source`: Where did this geotag come from? (exif, manual, inferred)
- `confidence`: How sure are we? (0.0-1.0 for auto-inferred locations)
- `location_name`: Human-readable name ("Raleigh, NC")
- `updated_at`, `updated_by`: Audit trail

**The database is optional and can be rebuilt anytime** - all GPS data lives in the image files.

## What We Built

### 1. Photo Library Audit Tool
```bash
tools/geotag_audit.py
```

Scanned your 1,434 photos:
- **942 (65.7%)** have complete GPS data ✓
- **479 (33.4%)** missing GPS data (need to fill in)
- **13 (0.9%)** incomplete GPS data

### 2. EXIF Read/Write Functions
```python
# Read GPS from image
geotag = extract_gps_from_exif('/path/to/photo.jpg')

# Write GPS to image (requires piexif library)
geotag = GeoTag(latitude=35.788, longitude=-78.873)
write_gps_to_exif('/path/to/photo.jpg', geotag)
```

### 3. Temporal Clustering Algorithm

Automatically suggests geotags for photos missing GPS:

**How it works:**
1. Group photos by time (within 1 hour by default)
2. For each time cluster:
   - Find photos WITH GPS (reference points)
   - Find photos WITHOUT GPS (need geotags)
   - Calculate centroid of reference points
   - Calculate confidence based on:
     - Number of reference photos (more = better)
     - Geographic spread (tighter = better)
     - Time gaps (smaller = better)
3. Suggest geotags with confidence >= 0.5

**Example:**
- 10 photos taken during a 30-minute period
- 7 have GPS (reference points)
- 3 don't have GPS (need geotags)
- All within 0.5km of each other
- **Result**: Suggest geotag for the 3 missing ones with 0.95 confidence

### 4. Complete Server API

**GET `/photo/<filename>/geotag`**
- Reads GPS from image EXIF
- Returns with metadata from database if available

**PUT `/photo/<filename>/geotag`**
- Writes GPS to image EXIF (**modifies the file**)
- Stores metadata in database

**POST `/photos/geotag/import-exif`**
- Indexes all photos (timestamps for clustering)
- **Does NOT modify files**

**POST `/photos/geotag/auto-infer`**
- Returns suggested geotags (temporal clustering)
- **Does NOT apply them** (manual review required)

**POST `/photos/geotag/batch-update`**
- Applies geotag to multiple photos
- **Writes to image EXIF** (permanent)

## Workflow Example

### Scenario: You have 15 photos from a vacation day, only 5 have GPS

**Step 1: Index your library**
```bash
curl -X POST http://localhost:8099/photos/geotag/import-exif
```

**Step 2: Get auto-inference suggestions**
```bash
curl -X POST http://localhost:8099/photos/geotag/auto-infer
```

Response shows:
```json
{
  "inferences": [
    {
      "filename": "IMG_5678.jpg",
      "geotag": {"latitude": 35.788, "longitude": -78.873},
      "confidence": 0.85,
      "reason": "5 ref photos, 10min apart, 0.3km spread"
    },
    ...10 more suggestions
  ]
}
```

**Step 3: Review suggestions in web UI** (Phase 2 - not built yet)
- See all 10 suggestions on a map
- Approve/reject each one
- Or manually adjust if location is slightly off

**Step 4: Apply approved suggestions**
```bash
curl -X POST http://localhost:8099/photos/geotag/batch-update \
  -d '{
    "filenames": ["IMG_5678.jpg", "IMG_5679.jpg", "IMG_5680.jpg"],
    "geotag": {
      "latitude": 35.788,
      "longitude": -78.873,
      "source": "inferred",
      "confidence": 0.85
    }
  }'
```

**Result**: GPS is now written to the image files. Portable and permanent!

## What's Next

### Phase 2: Web UI (Not Started)

Build a web interface for:
1. **Photo grid with status badges**
   - Green = has GPS
   - Yellow = auto-inference suggestion available
   - Red = no GPS data

2. **Interactive map (Leaflet.js)**
   - Show all geotagged photos on world map
   - Click photo to see on map
   - Click map to set location

3. **Auto-inference review workflow**
   - See all suggestions
   - Approve/reject with one click
   - Batch apply to multiple photos

4. **Manual editing**
   - Click on map to set location
   - Or enter lat/lon manually
   - Reverse geocoding for location names

### Phase 3: Roku Screensaver (After Web UI)

Add map overlay to screensaver:
1. Generate static world map image (1920x1080)
2. Calculate pin position from lat/lon
3. Overlay on photo during screensaver
4. Display location name if available

## Files Created

### Core Code
- `server/geotag_manager.py` - Geotag functions and database
- `server/server.py` - Updated with 6 new API endpoints
- `server/Dockerfile` - Added piexif dependency

### Tools
- `tools/geotag_audit.py` - Photo library audit script
- `tools/geotag_audit_report.json` - Audit results (942 have GPS)
- `tools/test_geotag_workflow.py` - Test EXIF read/write

### Documentation
- `docs/GEOTAG_ARCHITECTURE.md` - Complete system design
- `docs/AUTO_GEOTAG_RESEARCH.md` - Auto-tagging strategies
- `docs/GEOTAG_QUICKSTART.md` - API testing guide
- `docs/GEOTAG_SUMMARY.md` - This file

## Dependencies

### Required
- **Pillow** - Read EXIF data (already installed)
- **piexif** - Write EXIF data (**NEW** - added to Dockerfile)

### Optional
- **SQLite** - Built into Python
- **requests** - For reverse geocoding (future feature)

## Testing

### Test EXIF write on one image:
```bash
cd /export/git/3-bad-dogs/tools
python3 test_geotag_workflow.py /export/ciriolisaver/test.jpg
```

### Test full API:
```bash
# Start server
cd /export/git/3-bad-dogs/server
python3 server.py

# In another terminal:
# Index photos
curl -X POST http://localhost:8099/photos/geotag/import-exif

# Get suggestions
curl -X POST http://localhost:8099/photos/geotag/auto-infer | jq
```

## Key Decisions Made

### ✅ EXIF as source of truth
- **Pro**: Portable, standard, simple
- **Con**: Modifies original files (acceptable for geotags)

### ✅ Database for metadata only
- **Pro**: Can track source, confidence, location names
- **Con**: Extra complexity (but optional)

### ✅ Manual review of auto-inferences
- **Pro**: User has final say, no mistakes
- **Con**: More work (but safer)

### ✅ Write GPS to file, not just database
- **Pro**: Geotag travels with photo
- **Con**: Takes longer to apply (acceptable tradeoff)

## Questions?

**Q: What if I copy a photo to another computer?**
A: The GPS data goes with it (stored in EXIF). You lose the metadata (source, confidence, location_name) but the actual coordinates are portable.

**Q: Can I delete the database and start over?**
A: Yes! Just re-run the import to rebuild the index. All GPS data is safe in the image files.

**Q: What if auto-inference suggests wrong location?**
A: That's why we show confidence scores and require manual review in the web UI (Phase 2). Never auto-applies without approval.

**Q: Does this work with all photo formats?**
A: Works with JPEG, TIFF, PNG (if they support EXIF). Most photos are JPEG so you're covered.

**Q: Can I see the GPS in other photo apps?**
A: Yes! Standard EXIF format works with Google Photos, Apple Photos, Windows Photos, etc.

## Ready to Use

The server API is complete and tested. You can:
1. Index your photo library
2. Get auto-inference suggestions
3. Manually apply geotags via API

What's missing is the **web UI** to make this easy to use. That's Phase 2.

Want to test it on your photos? Or ready to build the web UI?
