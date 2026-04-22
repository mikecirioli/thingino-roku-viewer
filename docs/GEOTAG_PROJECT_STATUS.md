# Geotag Feature - Project Status & Roadmap

**Last Updated:** 2026-04-21  
**Status:** Phase 1 Complete | Phase 2 Complete | Phase 3 Partial

---

## Table of Contents
- [Executive Summary](#executive-summary)
- [Architecture Overview](#architecture-overview)
- [Phase 1: Foundation (COMPLETE)](#phase-1-foundation-complete)
- [Phase 2: Web UI (NOT STARTED)](#phase-2-web-ui-not-started)
- [Phase 3: Roku Screensaver (NOT STARTED)](#phase-3-roku-screensaver-not-started)
- [Files Created](#files-created)
- [Testing Status](#testing-status)
- [Dependencies](#dependencies)
- [Next Steps](#next-steps)

---

## Executive Summary

### Goal
Add geographic location display to the Roku screensaver by:
1. Cleaning up existing geotag data in photo library
2. Auto-inferring missing geotags where possible
3. Providing web UI for manual geotag management
4. Displaying location with world map pin on Roku screensaver

### Photo Library Status
- **Total photos:** 1,434
- **Have complete GPS:** 942 (65.7%) ✓
- **Missing GPS:** 479 (33.4%) ← need to fill these in
- **Incomplete GPS:** 13 (0.9%)

### Key Architecture Decision
**Image EXIF is the source of truth for GPS coordinates.**
- GPS data stored in image file (portable, standard)
- Database stores metadata only (source, confidence, location_name)
- All writes go to EXIF first, then optionally to database
- Database can be rebuilt anytime - GPS data is safe in images

### Progress
- **Phase 1 Complete:** Server API, EXIF read/write, temporal clustering, audit tools
- **Phase 2 Complete:** Web UI Geotags tab with Leaflet map, photo grid, batch editing, auto-inference review
- **Phase 3 Partial:** Roku screensaver displays "City, Country, DD-MM-YYYY" via X-Photo-Info header. World map overlay not yet implemented.

---

## Architecture Overview

### Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Photo Library                        │
│              (/export/ciriolisaver/)                   │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│
│  │  IMG_1.jpg   │  │  IMG_2.jpg   │  │  IMG_3.jpg   ││
│  │  ┌────────┐  │  │  ┌────────┐  │  │             ││
│  │  │GPS:    │  │  │  │GPS:    │  │  │  No GPS     ││
│  │  │35.788  │  │  │  │34.101  │  │  │             ││
│  │  │-78.873 │  │  │  │-118.34 │  │  │             ││
│  │  └────────┘  │  │  └────────┘  │  │             ││
│  │  EXIF ✓      │  │  EXIF ✓      │  │             ││
│  └──────────────┘  └──────────────┘  └──────────────┘│
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────────┐
          │    Server API (server.py)    │
          │                              │
          │  • Read GPS from EXIF        │
          │  • Write GPS to EXIF         │
          │  • Auto-infer missing GPS    │
          │  • Store metadata in DB      │
          └──────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
   ┌─────────────────┐     ┌──────────────────┐
   │  geotag_db      │     │  Client Apps     │
   │  (SQLite)       │     │                  │
   │                 │     │  • Web UI        │
   │  • source       │     │  • Roku app      │
   │  • confidence   │     │  • Future apps   │
   │  • location_name│     │                  │
   │  • audit trail  │     └──────────────────┘
   └─────────────────┘
     (metadata only)
```

### Key Principles

1. **EXIF as Source of Truth**
   - GPS coordinates (lat, lon, altitude) stored in image EXIF
   - Portable: copy photo → geotag goes with it
   - Standard: works with all photo apps
   - Permanent: survives database loss

2. **Database for Management Metadata**
   - Source tracking (exif, manual, inferred)
   - Confidence scores (0.0-1.0 for inferred)
   - Location names (reverse geocoded)
   - Audit trail (who/when updated)

3. **Manual Review Required**
   - Auto-inference never applies automatically
   - User reviews and approves suggestions
   - Prevents incorrect geotags

---

## Phase 1: Foundation (COMPLETE)

### 1.1 Photo Library Audit ✅

**Script:** `tools/geotag_audit.py`

**What it does:**
- Scans all images in photo directory
- Extracts GPS EXIF data using Pillow
- Categorizes: complete GPS, incomplete GPS, no GPS
- Generates JSON report

**Results:**
```
Total images:          1,434
✓ Complete GPS:          942 (65.7%)
⚠ Incomplete GPS:         13 (0.9%)
✗ No GPS:                479 (33.4%)
⚠ Errors:                  0 (0.0%)
```

**Output:** `tools/geotag_audit_report.json`

**Sample photos with GPS:**
- `185BD699-0DD1-49CA-98D4-3C2F378429AE.jpg`: 35.788508, -78.873086
- `71AFD5B6-3BEF-4761-B1F4-7096D065EB94.jpg`: 34.101781, -118.341483
- `B36B6BD1-6B2A-4228-86A4-FD7324B4F2A5.jpg`: 27.273783, -82.567886

**Sample photos missing GPS:**
- `01910_G.jpg`
- `10348440_10203961986802987_7892557044042546695_n.jpg` (Facebook download)
- `IMG_20150125_181042087_TOP.jpg` (has GPS version but no coordinates)

---

### 1.2 Geotag Manager Library ✅

**File:** `server/geotag_manager.py`

**Functions:**

#### EXIF Operations
```python
def extract_gps_from_exif(image_path: str) -> Optional[GeoTag]
```
- Reads GPS coordinates from image EXIF
- Converts DMS (degrees/minutes/seconds) to decimal
- Returns GeoTag object or None

```python
def write_gps_to_exif(image_path: str, geotag: GeoTag) -> bool
```
- Writes GPS coordinates to image EXIF
- Modifies the image file permanently
- Requires piexif library
- Returns True if successful

```python
def extract_exif_timestamp(image_path: str) -> Optional[int]
```
- Extracts photo creation time from EXIF
- Used for temporal clustering
- Returns Unix timestamp or None

#### Database Operations
```python
class GeotagDatabase:
    def add_photo(filename, filepath, exif_timestamp)
    def get_photo_id(filename)
    def set_geotag_metadata(filename, geotag)
    def get_geotag_metadata(filename)
    def list_photos_by_status(status)
    def get_all_with_geotags()
    def get_photos_without_geotags()
```

#### Temporal Clustering
```python
def cluster_photos_by_time(photos_with_timestamps, time_window=3600)
```
- Groups photos taken within time_window seconds
- Default: 1 hour (3600 seconds)
- Returns list of clusters

```python
def infer_geotags_from_cluster(cluster, all_geotags, min_refs=2)
```
- For each cluster, finds photos with/without GPS
- Calculates centroid of photos with GPS
- Infers location for photos without GPS
- Returns suggestions with confidence scores

```python
def haversine_distance(lat1, lon1, lat2, lon2)
```
- Calculates distance between two points on Earth
- Returns distance in kilometers
- Used for geographic spread calculation

#### Confidence Calculation
```python
def _calculate_confidence(num_refs, spread_km, time_delta_sec, cluster_size)
```
Weighted scoring:
- **30%** Reference count (more = better)
- **40%** Geographic spread (tighter = better)
- **30%** Time delta (smaller = better)

**Thresholds:**
- `0.9-1.0`: Very high confidence
- `0.7-0.9`: High confidence
- `0.5-0.7`: Medium confidence (review recommended)
- `<0.5`: Low confidence (not suggested)

---

### 1.3 Server API Endpoints ✅

**File:** `server/server.py` (integrated)

#### GET `/photo/<filename>/geotag`
Get geotag for a specific photo.

**Flow:**
1. Read GPS from image EXIF (source of truth)
2. Fetch metadata from database (if available)
3. Merge and return

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
    "altitude": 120.5,
    "location_name": "Raleigh, NC",
    "source": "manual",
    "confidence": 1.0,
    "updated_at": "2026-04-06T10:30:00Z",
    "updated_by": "user"
  }
}
```

#### PUT `/photo/<filename>/geotag`
Set geotag for a photo (manual edit).

**Flow:**
1. **Write GPS to image EXIF** (MUST succeed)
2. Store metadata in database (optional)

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

**Response:**
```json
{
  "status": "ok",
  "wrote_exif": true
}
```

⚠️ **Important:** This **modifies the image file**. GPS is now permanent.

#### GET `/photos/geotags?status=missing`
List photos filtered by geotag status.

**Status options:** `all`, `complete`, `missing`

**Example:**
```bash
curl http://localhost:8099/photos/geotags?status=missing
```

**Response:**
```json
{
  "photos": [
    {"filename": "01910_G.jpg", "geotag": null},
    {"filename": "IMG_5678.jpg", "geotag": null}
  ]
}
```

#### POST `/photos/geotag/import-exif`
Index all photos with their timestamps.

**Flow:**
1. Scan photo directory
2. For each photo:
   - Extract EXIF timestamp
   - Add to database
   - Check if GPS exists (count only)

**Does NOT modify files** - just indexes what's there.

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

#### POST `/photos/geotag/auto-infer`
Generate geotag suggestions using temporal clustering.

**Flow:**
1. Get all photos with GPS from EXIF
2. Get all photos without GPS from database
3. Cluster by time (default: 1 hour window)
4. For each cluster, infer locations
5. Return suggestions with confidence >= 0.5

**Does NOT apply suggestions** - just returns them for review.

**Request (optional):**
```json
{
  "time_window": 3600
}
```

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

#### POST `/photos/geotag/batch-update`
Apply geotag to multiple photos.

**Flow:**
1. For each filename:
   - **Write GPS to image EXIF** (permanent)
   - Store metadata in database

**Example:**
```bash
curl -X POST http://localhost:8099/photos/geotag/batch-update \
  -H "Content-Type: application/json" \
  -d '{
    "filenames": ["IMG_5678.jpg", "IMG_5679.jpg"],
    "geotag": {
      "latitude": 35.788,
      "longitude": -78.873,
      "location_name": "Vacation Day 2",
      "source": "inferred",
      "confidence": 0.85,
      "updated_by": "user"
    }
  }'
```

**Response:**
```json
{
  "status": "ok",
  "updated": 2,
  "errors": 0
}
```

⚠️ **Important:** This **modifies image files**. Use after reviewing suggestions.

---

### 1.4 Testing Tools ✅

#### Audit Script
**File:** `tools/geotag_audit.py`

```bash
python3 tools/geotag_audit.py /export/ciriolisaver
```

Outputs:
- Console summary
- `tools/geotag_audit_report.json`

#### Workflow Test
**File:** `tools/test_geotag_workflow.py`

```bash
python3 tools/test_geotag_workflow.py /path/to/test.jpg
```

Tests:
1. Read existing GPS from EXIF
2. Write new GPS to EXIF
3. Read back and verify
4. Optionally restore original

---

### 1.5 Database Schema ✅

**Location:** `/data/geotags/geotags.db` (SQLite)

#### Table: `photos`
```sql
CREATE TABLE photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    file_hash TEXT,                    -- SHA256 for change detection
    last_modified INTEGER,              -- Unix timestamp
    exif_timestamp INTEGER              -- For clustering
);

CREATE INDEX idx_photos_filename ON photos(filename);
CREATE INDEX idx_photos_timestamp ON photos(exif_timestamp);
```

#### Table: `geotags`
```sql
CREATE TABLE geotags (
    photo_id INTEGER PRIMARY KEY,
    latitude REAL NOT NULL,             -- Cached from EXIF
    longitude REAL NOT NULL,            -- Cached from EXIF
    altitude REAL,                      -- Cached from EXIF
    location_name TEXT,                 -- Reverse geocoded
    source TEXT NOT NULL,               -- exif|manual|inferred|google_photos
    confidence REAL NOT NULL DEFAULT 1.0,
    updated_at INTEGER NOT NULL,        -- Unix timestamp
    updated_by TEXT,                    -- user|exif_import|temporal_cluster
    FOREIGN KEY (photo_id) REFERENCES photos(id)
);

CREATE INDEX idx_geotags_location ON geotags(latitude, longitude);
```

**Note:** Coordinates in database are **cached copies** for querying. EXIF is source of truth.

---

### 1.6 Documentation ✅

#### Core Documentation
- **`docs/GEOTAG_ARCHITECTURE.md`** - Complete system architecture
- **`docs/GEOTAG_DESIGN.md`** - Original design document
- **`docs/AUTO_GEOTAG_RESEARCH.md`** - Auto-tagging strategies and research
- **`docs/GEOTAG_QUICKSTART.md`** - API testing guide
- **`docs/GEOTAG_SUMMARY.md`** - Executive summary
- **`docs/GEOTAG_PROJECT_STATUS.md`** - This file

#### Integration Documentation
- **`server/geotag_integration.py`** - Code snippets and integration notes

---

## Phase 2: Web UI (NOT STARTED)

### Goal
Build web interface for geotag management and review.

### 2.1 Photo Grid View

**Location:** `/web` tab in `web/web_ui.html`

**Features:**
- Grid of photo thumbnails
- Status badges:
  - 🟢 Green = has GPS
  - 🟡 Yellow = auto-inference suggestion available
  - 🔴 Red = no GPS data
- Click photo to:
  - View full size
  - See current geotag
  - Edit manually

**Implementation:**
```javascript
// Fetch photos with status
fetch('/photos/geotags?status=all')
  .then(r => r.json())
  .then(data => renderPhotoGrid(data.photos));

function renderPhotoGrid(photos) {
  const grid = document.getElementById('photo-grid');
  photos.forEach(photo => {
    const status = photo.geotag ? 'has-gps' : 'no-gps';
    const badge = photo.geotag ? '🟢' : '🔴';
    
    grid.innerHTML += `
      <div class="photo-card ${status}">
        <img src="/library/thumb?path=${photo.filename}" />
        <div class="badge">${badge}</div>
        <div class="filename">${photo.filename}</div>
      </div>
    `;
  });
}
```

---

### 2.2 Interactive Map

**Library:** Leaflet.js (https://leafletjs.com/)

**Features:**
- World map showing all geotagged photos
- Cluster markers for dense areas
- Click photo marker to see details
- Click anywhere on map to set location
- Search box for location lookup

**Implementation:**
```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>

<div id="map" style="height: 600px;"></div>
```

```javascript
// Initialize map
const map = L.map('map').setView([35.7796, -78.6382], 4);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

// Add marker clustering
const markers = L.markerClusterGroup();

// Fetch all photos with GPS
fetch('/photos/geotags?status=complete')
  .then(r => r.json())
  .then(data => {
    data.photos.forEach(photo => {
      const marker = L.marker([photo.geotag.latitude, photo.geotag.longitude]);
      marker.bindPopup(`
        <img src="/library/thumb?path=${photo.filename}" width="200" />
        <br>${photo.filename}
        <br>${photo.geotag.location_name || 'Unknown location'}
      `);
      markers.addLayer(marker);
    });
    map.addLayer(markers);
  });

// Click to set location
map.on('click', (e) => {
  const {lat, lng} = e.latlng;
  // Show dialog to apply to selected photos
  applyGeotag(selectedPhotos, lat, lng);
});
```

---

### 2.3 Auto-Inference Review Workflow

**UI Flow:**
1. User clicks "Auto-Infer Locations"
2. Server runs temporal clustering
3. Display suggestions grouped by confidence:
   - High (0.8-1.0): Auto-approve option
   - Medium (0.6-0.8): Review individually
   - Low (0.5-0.6): Manual review required

**Implementation:**
```javascript
async function runAutoInference() {
  showSpinner('Analyzing photos...');
  
  const response = await fetch('/photos/geotag/auto-infer', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({time_window: 3600})
  });
  
  const {inferences} = await response.json();
  
  // Group by confidence
  const high = inferences.filter(i => i.geotag.confidence >= 0.8);
  const medium = inferences.filter(i => i.geotag.confidence >= 0.6 && i.geotag.confidence < 0.8);
  const low = inferences.filter(i => i.geotag.confidence < 0.6);
  
  displayInferenceResults({high, medium, low});
}

function displayInferenceResults({high, medium, low}) {
  // Show suggestions on map with color coding
  // Green pins = high confidence
  // Yellow pins = medium confidence
  // Red pins = low confidence
  
  // Bulk approve button for high confidence
  document.getElementById('approve-all-high').onclick = () => {
    applyBatchGeotags(high);
  };
}

async function applyBatchGeotags(inferences) {
  for (const inf of inferences) {
    await fetch(`/photo/${inf.filename}/geotag`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(inf.geotag)
    });
  }
  
  showToast(`✓ Applied ${inferences.length} geotags`);
  refreshPhotoGrid();
}
```

---

### 2.4 Manual Editing Dialog

**Features:**
- Click photo or map to open edit dialog
- Manual lat/lon entry
- Click-on-map location picker
- Reverse geocoding for location name
- Altitude (optional)

**Implementation:**
```html
<dialog id="edit-geotag-dialog">
  <h2>Edit Geotag</h2>
  <img id="edit-photo" src="" />
  
  <form id="edit-form">
    <label>
      Latitude:
      <input type="number" name="latitude" step="0.000001" required />
    </label>
    
    <label>
      Longitude:
      <input type="number" name="longitude" step="0.000001" required />
    </label>
    
    <label>
      Location Name:
      <input type="text" name="location_name" />
      <button type="button" onclick="reverseGeocode()">🔍 Lookup</button>
    </label>
    
    <label>
      Altitude (m):
      <input type="number" name="altitude" />
    </label>
    
    <div class="map-picker" id="location-picker"></div>
    
    <button type="submit">Save to Image EXIF</button>
    <button type="button" onclick="closeDialog()">Cancel</button>
  </form>
</dialog>
```

```javascript
async function saveGeotag(filename, geotag) {
  const response = await fetch(`/photo/${filename}/geotag`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(geotag)
  });
  
  if (response.ok) {
    showToast('✓ Geotag saved to image');
  } else {
    showToast('✗ Failed to save geotag', 'error');
  }
}

async function reverseGeocode() {
  const lat = document.querySelector('[name=latitude]').value;
  const lon = document.querySelector('[name=longitude]').value;
  
  // Use Nominatim (OpenStreetMap)
  const url = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`;
  const response = await fetch(url);
  const data = await response.json();
  
  document.querySelector('[name=location_name]').value = data.display_name;
}
```

---

### 2.5 Batch Operations

**Features:**
- Select multiple photos
- Apply same geotag to all
- Useful for vacation photos taken at same location

**Implementation:**
```javascript
let selectedPhotos = [];

function togglePhotoSelection(filename) {
  if (selectedPhotos.includes(filename)) {
    selectedPhotos = selectedPhotos.filter(f => f !== filename);
  } else {
    selectedPhotos.push(filename);
  }
  updateSelectionUI();
}

async function applyGeotagToSelected(geotag) {
  await fetch('/photos/geotag/batch-update', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      filenames: selectedPhotos,
      geotag: geotag
    })
  });
  
  showToast(`✓ Applied geotag to ${selectedPhotos.length} photos`);
  selectedPhotos = [];
  refreshPhotoGrid();
}
```

---

### 2.6 Filtering & Search

**Features:**
- Filter by status (has GPS / missing GPS / suggested)
- Filter by date range
- Filter by location name
- Search by filename

**Implementation:**
```javascript
function applyFilters() {
  const status = document.getElementById('filter-status').value;
  const dateFrom = document.getElementById('filter-date-from').value;
  const dateTo = document.getElementById('filter-date-to').value;
  const search = document.getElementById('search-box').value;
  
  let url = `/photos/geotags?status=${status}`;
  if (dateFrom) url += `&date_from=${dateFrom}`;
  if (dateTo) url += `&date_to=${dateTo}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  
  fetch(url)
    .then(r => r.json())
    .then(data => renderPhotoGrid(data.photos));
}
```

---

### 2.7 UI Mockup

```
┌─────────────────────────────────────────────────────────────────────┐
│  3 Bad Dogs - Geotag Management                        [Settings]   │
├─────────────────────────────────────────────────────────────────────┤
│  [Live View] [Time-lapse] [Geotags] ← NEW TAB                      │
├─────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────┐  ┌─────────────────────────────────────┐│
│  │ Photo Grid            │  │ Map View                            ││
│  ├───────────────────────┤  │                                     ││
│  │ Status: [All▾]        │  │  🗺️ Interactive World Map            ││
│  │ Search: [_______]     │  │                                     ││
│  │ Date: [____] to [___] │  │  • Green pins = photos with GPS    ││
│  │                       │  │  • Red pins = suggested locations  ││
│  │ [Auto-Infer] [Batch]  │  │  • Click to set location           ││
│  ├───────────────────────┤  │                                     ││
│  │ 🟢 IMG_1234.jpg       │  │                                     ││
│  │ 🔴 IMG_5678.jpg       │  │                                     ││
│  │ 🟡 IMG_9012.jpg       │  │                                     ││
│  │ 🟢 IMG_3456.jpg       │  │                                     ││
│  │ 🔴 IMG_7890.jpg       │  │                                     ││
│  │ ...                   │  │                                     ││
│  └───────────────────────┘  └─────────────────────────────────────┘│
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Auto-Inference Results                                       │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │ High Confidence (157): [Approve All] [Review]               │  │
│  │ Medium Confidence (84): [Review]                            │  │
│  │ Low Confidence (23): [Review]                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 2.8 Phase 2 Estimated Effort

**Components:**
- Photo grid view: 4-6 hours
- Interactive map (Leaflet): 6-8 hours
- Auto-inference review UI: 4-6 hours
- Manual editing dialog: 3-4 hours
- Batch operations: 2-3 hours
- Filtering/search: 2-3 hours
- Reverse geocoding integration: 2-3 hours
- Testing & polish: 4-6 hours

**Total:** 27-39 hours

---

## Phase 3: Roku Screensaver (NOT STARTED)

### Goal
Display location with world map pin on Roku screensaver when photo has geotag.

### 3.1 Server Enhancement

**Update `/random` endpoint to include geotag:**

```python
def serve_random(self, parsed):
    photo_path = random.choice(get_photos())
    filename = os.path.basename(photo_path)
    
    # Get geotag if available
    geotag = extract_gps_from_exif(photo_path)
    
    # Add geotag to response headers
    if geotag:
        self.send_header('X-Photo-Geotag', json.dumps({
            'latitude': geotag.latitude,
            'longitude': geotag.longitude,
            'location_name': geotag.location_name
        }))
    
    # Serve image...
```

**Or new endpoint `/random/info`:**
```json
{
  "url": "/photo/IMG_1234.jpg",
  "geotag": {
    "latitude": 35.788,
    "longitude": -78.873,
    "location_name": "Raleigh, NC"
  }
}
```

---

### 3.2 World Map Generation

**Option A: Static Map Image**
- Pre-generate world map PNG (1920x1080)
- Equirectangular projection
- Transparent background or semi-transparent
- Saved at `roku/images/world-map.png`

**Option B: Mapbox Static API**
- Generate on-demand via Mapbox Static Images API
- Free tier: 50,000 requests/month
- Overlay pin marker

**Recommendation:** Static PNG (simpler, no API dependency)

**Map Requirements:**
- 1920x1080 resolution
- Equirectangular projection (for easy lat/lon → pixel conversion)
- Light/minimal design (doesn't distract from photo)
- Optional: transparent or 50% opacity

---

### 3.3 Pin Position Calculation

**Equirectangular projection formula:**
```brightscript
function latLonToPixel(lat as Float, lon as Float, width as Integer, height as Integer) as Object
    ' Convert latitude/longitude to pixel position
    ' World map is equirectangular projection
    
    x = (lon + 180) * (width / 360)
    y = (90 - lat) * (height / 180)
    
    return {x: x, y: y}
end function
```

**Example:**
- Photo taken at: 35.788°N, 78.873°W
- Map size: 1920x1080
- Pin position: x = 1078, y = 291

---

### 3.4 Roku Component Changes

**Update `ScreensaverScene.xml`:**

```xml
<!-- Add world map overlay -->
<Poster id="worldMap" width="1920" height="1080"
        translation="[0,0]" opacity="0.0" visible="false"
        uri="pkg:/images/world-map.png" />

<!-- Add location pin -->
<Rectangle id="locationPin" width="20" height="30"
           color="#FF0000" opacity="0.0" visible="false" />

<!-- Add location name label -->
<Label id="locationLabel" text=""
       color="#FFFFFF" opacity="0.0" visible="false"
       horizAlign="center" />
```

**Update `ScreensaverScene.brs`:**

```brightscript
sub loadNextImage()
    ' ... existing code ...
    
    ' Check if photo has geotag
    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onPhotoInfo")
    task.request = {url: m.SERVER_URL + "/random/info"}
    task.control = "run"
end sub

sub onPhotoInfo(event as object)
    text = event.getData()
    if text <> invalid and text <> ""
        json = ParseJSON(text)
        if json <> invalid and json.geotag <> invalid
            showLocationOverlay(json.geotag)
        else
            hideLocationOverlay()
        end if
    end if
end sub

sub showLocationOverlay(geotag as Object)
    ' Calculate pin position
    pos = latLonToPixel(geotag.latitude, geotag.longitude, 1920, 1080)
    
    ' Show map overlay
    m.worldMap.visible = true
    m.worldMap.opacity = 0.5
    
    ' Position and show pin
    m.locationPin.translation = [pos.x - 10, pos.y - 30]
    m.locationPin.visible = true
    m.locationPin.opacity = 0.9
    
    ' Show location name
    if geotag.location_name <> invalid and geotag.location_name <> ""
        m.locationLabel.text = geotag.location_name
        m.locationLabel.translation = [pos.x, pos.y + 10]
        m.locationLabel.visible = true
        m.locationLabel.opacity = 0.9
    end if
    
    ' Fade in animation
    m.fadeInMap.control = "start"
end sub

sub hideLocationOverlay()
    m.worldMap.visible = false
    m.locationPin.visible = false
    m.locationLabel.visible = false
end sub

function latLonToPixel(lat as Float, lon as Float, width as Integer, height as Integer) as Object
    x = (lon + 180) * (width / 360)
    y = (90 - lat) * (height / 180)
    return {x: x, y: y}
end function
```

---

### 3.5 Animation

**Fade in sequence:**
1. Photo fades in (existing)
2. Wait 2 seconds
3. Map overlay fades in (0.5 second)
4. Pin fades in (0.3 second)
5. Location name fades in (0.3 second)
6. All remain visible for photo duration
7. Fade out with photo transition

**XML animations:**
```xml
<Animation id="fadeInMap" duration="0.5" repeat="false" easeFunction="inOutCubic">
  <FloatFieldInterpolator key="[0.0, 1.0]" keyValue="[0.0, 0.5]"
                          fieldToInterp="worldMap.opacity" />
</Animation>

<Animation id="fadeInPin" duration="0.3" repeat="false" easeFunction="inOutCubic">
  <FloatFieldInterpolator key="[0.0, 1.0]" keyValue="[0.0, 0.9]"
                          fieldToInterp="locationPin.opacity" />
</Animation>
```

---

### 3.6 Design Considerations

**Map style:**
- Minimal design (lines only, no country fills)
- Light gray or white lines
- 50% opacity (doesn't distract from photo)
- High contrast pin (bright red or orange)

**Pin design:**
- Simple red/orange pin icon
- 20x30 pixels (visible but not too large)
- Drop shadow for visibility on light photos

**Location name:**
- White text with black outline/shadow
- Positioned below pin
- Truncate long names (max 30 chars)

**Fallback:**
- If no geotag: no map overlay shown (existing behavior)
- If map image fails to load: show location name only

---

### 3.7 Phase 3 Estimated Effort

**Components:**
- World map image generation/selection: 2-3 hours
- Server endpoint enhancement: 1-2 hours
- Roku XML/BRS changes: 3-4 hours
- Animation implementation: 2-3 hours
- Testing & polish: 2-3 hours

**Total:** 10-15 hours

---

## Files Created

### Phase 1 Files

**Server Code:**
- `server/geotag_manager.py` (new, 700+ lines)
- `server/server.py` (modified, added ~300 lines)
- `server/Dockerfile` (modified, added piexif)
- `server/geotag_integration.py` (documentation)

**Tools:**
- `tools/geotag_audit.py` (new, 200+ lines)
- `tools/geotag_audit_report.json` (generated)
- `tools/test_geotag_workflow.py` (new, 200+ lines)

**Documentation:**
- `docs/GEOTAG_ARCHITECTURE.md` (new)
- `docs/GEOTAG_DESIGN.md` (new)
- `docs/AUTO_GEOTAG_RESEARCH.md` (new)
- `docs/GEOTAG_QUICKSTART.md` (new)
- `docs/GEOTAG_SUMMARY.md` (new)
- `docs/GEOTAG_PROJECT_STATUS.md` (new, this file)

**Database:**
- `/data/geotags/geotags.db` (auto-created on first run)

---

## Testing Status

### Unit Tests: Not Written
Phase 1 was built without formal unit tests. Consider adding:
- `tests/test_geotag_manager.py`
- `tests/test_temporal_clustering.py`
- `tests/test_confidence_calculation.py`

### Manual Testing: Partial
- ✅ EXIF read functions tested with 1,434 real photos
- ✅ Audit script runs successfully
- ⏸️ EXIF write not tested on real photos (need piexif)
- ⏸️ API endpoints not tested end-to-end
- ⏸️ Temporal clustering not tested with real data

### Integration Testing: Not Done
- [ ] Server startup with geotag features
- [ ] Full API workflow (import → infer → apply)
- [ ] Database persistence across restarts
- [ ] Docker deployment

---

## Dependencies

### Python Libraries

**Existing:**
- `Pillow` - Read EXIF (installed)
- `PyYAML` - Config files (installed)
- `requests` - HTTP requests (installed)

**New (Phase 1):**
- `piexif` - Write EXIF ✓ Added to Dockerfile

**Future (Phase 2):**
- None (web UI is pure HTML/CSS/JS)

**Future (Phase 3):**
- None (Roku is BrightScript)

### JavaScript Libraries (Phase 2)

**Leaflet.js:**
- `leaflet@1.9.4` - Map library
- `leaflet.markercluster@1.5.3` - Marker clustering

**Optional:**
- `nominatim` - Reverse geocoding (free, no key)

---

## Next Steps

### Immediate Actions

1. **Test Phase 1 Implementation**
   ```bash
   # Install piexif
   pip install piexif
   
   # Test EXIF write
   python3 tools/test_geotag_workflow.py /export/ciriolisaver/test.jpg
   
   # Start server
   cd server && python3 server.py
   
   # Index photos
   curl -X POST http://localhost:8099/photos/geotag/import-exif
   
   # Get suggestions
   curl -X POST http://localhost:8099/photos/geotag/auto-infer
   ```

2. **Review Temporal Clustering Results**
   - How many suggestions?
   - What are the confidence scores?
   - Do they make sense geographically?

3. **Commit Phase 1 Changes**
   ```bash
   git add server/ tools/ docs/ 
   git commit -m "feat: geotag management system - Phase 1 foundation
   
   - EXIF-based geotag storage (image file is source of truth)
   - Temporal clustering for auto-inference
   - Complete REST API (6 endpoints)
   - Database for metadata tracking
   - Audit and testing tools
   
   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
   ```

### Phase 2 Kickoff

**Prerequisites:**
- Phase 1 tested and working
- Sample auto-inference results reviewed
- UI mockup approved

**First Tasks:**
1. Add new "Geotags" tab to `web/web_ui.html`
2. Implement photo grid view with status badges
3. Integrate Leaflet.js map
4. Build manual editing dialog

**Timeline:** 2-4 weeks (part-time)

### Phase 3 Kickoff

**Prerequisites:**
- Phase 2 complete (web UI functional)
- At least 80% of photos geotagged
- World map design finalized

**First Tasks:**
1. Generate/select world map image
2. Update `/random` endpoint with geotag
3. Add map overlay to ScreensaverScene.xml
4. Test on Roku device

**Timeline:** 1-2 weeks (part-time)

---

## Open Questions

### Phase 1
- [ ] Should we write unit tests before Phase 2?
- [ ] Need to test with real photo modifications?
- [ ] Deploy to Docker and test on optiplex?

### Phase 2
- [ ] Web UI design preferences? (Material Design, Bootstrap, custom?)
- [ ] Reverse geocoding service? (Nominatim, BigDataCloud, paid service?)
- [ ] Should we support photo upload/import in web UI?
- [ ] Privacy mode to exclude home location?

### Phase 3
- [ ] World map style preference? (minimalist, detailed, dark/light?)
- [ ] Pin design? (standard pin, custom icon, animated?)
- [ ] Should map show on ALL photos or only those with geotags?
- [ ] Option to hide map in screensaver settings?

---

## Risk Assessment

### Low Risk ✅
- EXIF read/write (well-tested library)
- Database schema (simple, standard SQLite)
- API design (RESTful, follows conventions)

### Medium Risk ⚠️
- Temporal clustering accuracy (depends on data quality)
- Confidence scoring calibration (may need tuning)
- Web UI complexity (lots of moving parts)

### High Risk 🚨
- **Modifying user's photo files** (EXIF write is permanent)
  - Mitigation: Test thoroughly, show warnings, allow restore
- **Performance with large libraries** (>10k photos)
  - Mitigation: Pagination, lazy loading, database indexes
- **Reverse geocoding rate limits** (free APIs have limits)
  - Mitigation: Cache results, implement retry logic

---

## Success Metrics

### Phase 1 (Current)
- ✅ Audit completes without errors
- ⏸️ EXIF write verified on test images
- ⏸️ Auto-inference generates reasonable suggestions
- ⏸️ API endpoints respond correctly

### Phase 2 (Target)
- User can geotag 100+ photos in <1 hour
- Auto-inference suggestions are 80%+ accurate
- Web UI is responsive and intuitive
- Zero data loss or corruption

### Phase 3 (Target)
- Map overlay renders correctly on Roku
- Pin position is accurate (±50 pixels)
- No performance impact on screensaver
- Feature is optional (can be disabled)

---

## Conclusion

**Phase 1 is architecturally complete** with a solid foundation:
- EXIF-based storage (portable, standard)
- Temporal clustering (smart auto-inference)
- Complete API (ready for web UI)
- Comprehensive documentation

**Phase 2 is the critical path** - web UI makes the feature usable.

**Phase 3 is the payoff** - beautiful location display on Roku screensaver.

**Estimated total project time:** 40-60 hours across all phases.

---

**Next action:** Test Phase 1 on your photo library and review auto-inference results!
