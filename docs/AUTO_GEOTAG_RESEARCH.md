# Auto-Geotagging Research & Implementation Guide

## Executive Summary

For the 479 photos (33%) missing GPS data, we have several strategies ranked by feasibility and confidence:

1. **Temporal Clustering** (BEST) - 80-90% coverage at medium-high confidence
2. **Filename Pattern Analysis** (GOOD) - 40-60% coverage at medium confidence  
3. **Google Photos API** (IF AVAILABLE) - High confidence but requires API access
4. **ML Landmark Detection** (FUTURE) - High effort, variable confidence

## Strategy 1: Temporal Clustering (RECOMMENDED FIRST)

### Concept
Photos taken close together in time are likely taken at the same location. If some photos in a time cluster have GPS, infer location for others.

### Algorithm

```python
def cluster_by_time(photos, time_window=3600):
    """
    Group photos within time_window seconds of each other
    
    Args:
        photos: List of photo metadata with timestamps and optional GPS
        time_window: Seconds (default: 3600 = 1 hour)
    
    Returns:
        List of clusters, each containing photos taken nearby in time
    """
    # Sort by timestamp
    sorted_photos = sorted(photos, key=lambda p: p.timestamp)
    
    clusters = []
    current_cluster = [sorted_photos[0]]
    
    for photo in sorted_photos[1:]:
        time_delta = photo.timestamp - current_cluster[-1].timestamp
        
        if time_delta <= time_window:
            current_cluster.append(photo)
        else:
            clusters.append(current_cluster)
            current_cluster = [photo]
    
    if current_cluster:
        clusters.append(current_cluster)
    
    return clusters

def infer_geotags_from_cluster(cluster):
    """
    Infer geotags for photos without GPS in a cluster
    """
    # Separate photos with and without GPS
    with_gps = [p for p in cluster if p.has_gps]
    without_gps = [p for p in cluster if not p.has_gps]
    
    if len(with_gps) < 2:
        # Need at least 2 reference points
        return []
    
    # Calculate centroid of reference photos
    avg_lat = sum(p.lat for p in with_gps) / len(with_gps)
    avg_lon = sum(p.lon for p in with_gps) / len(with_gps)
    
    # Calculate geographic spread (standard deviation)
    lat_stddev = calculate_stddev([p.lat for p in with_gps])
    lon_stddev = calculate_stddev([p.lon for p in with_gps])
    spread_km = haversine(avg_lat - lat_stddev, avg_lon, 
                          avg_lat + lat_stddev, avg_lon)
    
    inferred = []
    for photo in without_gps:
        # Calculate confidence based on:
        # - Number of reference points
        # - Geographic spread
        # - Time delta from nearest reference
        
        time_delta = min(abs(photo.timestamp - ref.timestamp) 
                        for ref in with_gps)
        
        confidence = calculate_confidence(
            num_refs=len(with_gps),
            spread_km=spread_km,
            time_delta_sec=time_delta,
            cluster_size=len(cluster)
        )
        
        if confidence >= 0.5:  # Only suggest if confidence >= 50%
            inferred.append({
                'photo': photo,
                'lat': avg_lat,
                'lon': avg_lon,
                'confidence': confidence,
                'reason': f'Clustered with {len(with_gps)} GPS photos, '
                         f'{time_delta/60:.0f}min apart, {spread_km:.1f}km spread'
            })
    
    return inferred

def calculate_confidence(num_refs, spread_km, time_delta_sec, cluster_size):
    """
    Calculate confidence score 0.0-1.0 for inferred geotag
    
    High confidence:
    - Many reference photos (5+)
    - Small geographic spread (<0.5km = walking around)
    - Small time delta (<15 min)
    
    Low confidence:
    - Few reference photos (2)
    - Large spread (>10km = driving around)
    - Large time delta (>1 hour)
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
```

### Expected Results
Based on typical photo patterns:
- **High confidence (>0.8)**: ~30-40% of missing photos
  - Burst photos, vacation sequences
- **Medium confidence (0.6-0.8)**: ~20-30% 
  - Same-day photos with some time gaps
- **Low confidence (<0.6)**: ~10-20%
  - Outliers, insufficient data

### Implementation Priority: **HIGH**
This should be the first auto-tagging feature implemented.

## Strategy 2: Filename Pattern Analysis

### Concept
Photos with similar filenames often come from the same source/time/place.

### Patterns to Detect

1. **iPhone Sequential**
   - Pattern: `IMG_NNNN.jpg` where NNNN increments
   - Photos with adjacent numbers likely from same session
   - Example: `IMG_1234.jpg` through `IMG_1250.jpg` = same trip

2. **Facebook Download**
   - Pattern: `NNNNNNNN_10203961986802987_NNNNNNNNNNNNNN_n.jpg`
   - Long numeric IDs indicate album/event
   - Middle segment (10203...) often same for related photos
   
3. **Android/Camera**
   - Pattern: `IMG_YYYYMMDD_HHMMSS.jpg`
   - Already has timestamp in filename
   - Cluster by date prefix

4. **Screenshot Pattern**
   - Pattern: `Screenshot_YYYY-MM-DD-HH-MM-SS.png`
   - Likely taken at home location

### Algorithm

```python
def analyze_filename_patterns(photos_without_gps):
    """
    Group photos by filename pattern and suggest batch locations
    """
    patterns = defaultdict(list)
    
    for photo in photos_without_gps:
        # Extract pattern
        if re.match(r'IMG_\d{4}\.jpg', photo.filename):
            # iPhone sequential - extract number
            num = int(re.search(r'\d{4}', photo.filename).group())
            patterns[('iphone_seq', num // 100)].append(photo)
        
        elif re.match(r'\d+_\d+_\d+_n\.jpg', photo.filename):
            # Facebook - extract middle segment
            middle = photo.filename.split('_')[1]
            patterns[('facebook', middle)].append(photo)
        
        elif re.match(r'IMG_\d{8}_\d{6}', photo.filename):
            # Android - extract date
            date = re.search(r'\d{8}', photo.filename).group()
            patterns[('android', date)].append(photo)
    
    # For each pattern group, find reference photos with GPS
    suggestions = []
    for (pattern_type, pattern_key), group in patterns.items():
        if len(group) < 3:  # Skip small groups
            continue
        
        # Look for nearby photos (by filename or timestamp) that have GPS
        reference_photos = find_reference_photos(group, all_photos)
        
        if reference_photos:
            suggestions.append({
                'group': group,
                'pattern': pattern_type,
                'suggested_location': average_location(reference_photos),
                'confidence': 0.6,  # Medium confidence
                'reason': f'{len(group)} photos matching pattern {pattern_type}'
            })
    
    return suggestions
```

### Expected Results
- **Coverage**: 40-60% of missing photos
- **Confidence**: Medium (0.5-0.7)
- **Requires manual review**: Yes, show batches for user approval

### Implementation Priority: **MEDIUM**
Implement after temporal clustering.

## Strategy 3: Google Photos API

### Concept
If photos are backed up to Google Photos, Google may have added location data.

### Requirements
- User must have Google Photos backup enabled
- Photos must be uploaded to Google Photos
- Google Photos API access (free tier: 10k requests/day)

### API Endpoints

```python
# List all photos from Google Photos
GET https://photoslibrary.googleapis.com/v1/mediaItems

# Get specific photo metadata
GET https://photoslibrary.googleapis.com/v1/mediaItems/{mediaItemId}

# Response includes location if available:
{
  "id": "...",
  "description": "...",
  "mimeType": "image/jpeg",
  "mediaMetadata": {
    "creationTime": "2020-01-15T10:30:00Z",
    "width": "4032",
    "height": "3024",
    "photo": {},
    "location": {
      "latitude": 37.7749,
      "longitude": -122.4194,
      "locationName": "San Francisco, CA"
    }
  }
}
```

### Matching Strategy
Match local files to Google Photos by:
1. **Filename** (if preserved)
2. **EXIF creation time** (most reliable)
3. **File hash** (if available)

### Expected Results
- **Coverage**: Variable (depends on user's backup habits)
- **Confidence**: High (0.9) - Google's data is usually accurate
- **Limitations**: 
  - Requires OAuth setup
  - Not all users have Google Photos
  - Photos must be uploaded

### Implementation Priority: **LOW**
Nice to have, but complex setup. Implement after core features work.

## Strategy 4: ML Landmark Detection

### Concept
Use computer vision to identify famous landmarks, then geocode.

### Services

1. **Google Cloud Vision API**
   - `LANDMARK_DETECTION` feature
   - Free tier: 1000 requests/month
   - Returns landmark name + lat/lon

2. **AWS Rekognition**
   - Celebrity/landmark detection
   - Similar pricing

### Example

```python
from google.cloud import vision

client = vision.ImageAnnotatorClient()

with open('photo.jpg', 'rb') as f:
    image = vision.Image(content=f.read())

response = client.landmark_detection(image=image)
landmarks = response.landmark_annotations

if landmarks:
    landmark = landmarks[0]
    print(f"Detected: {landmark.description}")
    lat = landmark.locations[0].lat_lng.latitude
    lon = landmark.locations[0].lat_lng.longitude
```

### Expected Results
- **Coverage**: 5-10% (only photos with recognizable landmarks)
- **Confidence**: High for famous landmarks (0.9), low otherwise
- **Cost**: Can get expensive at scale

### Implementation Priority: **VERY LOW**
Only useful for small subset of photos. Implement much later if needed.

## Strategy 5: Manual Pattern Recognition Tools

### Assist User in Finding Patterns

Build UI tools to help user quickly apply location to batches:

1. **Date Range Selector**
   - "All photos from June 15-22, 2023 were taken in Paris"
   - Apply location to entire range

2. **Filename Batch Selector**
   - Show photos grouped by filename pattern
   - "Select all IMG_12XX.jpg photos" → apply location

3. **Visual Clustering**
   - Show thumbnails sorted by time
   - User can draw box around related photos
   - Apply same location to selection

4. **Smart Suggestions**
   - "You have 15 photos from 2024-08-10 without GPS"
   - "12 nearby photos have GPS showing 'Los Angeles, CA'"
   - "Apply this location to all 15?" [Yes] [No] [Review]

### Implementation Priority: **HIGH**
This is the most practical approach - semi-automated with human verification.

## Recommended Implementation Order

### Phase 1 (IMMEDIATE)
1. ✅ Audit existing geotag data (DONE)
2. Build temporal clustering algorithm
3. Build web UI to show suggestions
4. Manual approval workflow

### Phase 2 (NEAR TERM)
1. Filename pattern detection
2. Date range batch selector
3. Reverse geocoding integration

### Phase 3 (FUTURE)
1. Google Photos API integration (if requested)
2. ML landmark detection (if budget allows)

## Tools & Libraries

### Python Libraries
```bash
pip install Pillow          # EXIF reading (already installed)
pip install geopy           # Distance calculations
pip install scikit-learn    # Clustering algorithms (optional)
pip install requests        # HTTP for geocoding APIs
```

### JavaScript Libraries (for web UI)
```html
<!-- Map display -->
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />

<!-- Marker clustering -->
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
```

## Privacy Considerations

### Home Location Detection
Many photos without GPS are taken at home. Auto-infer home location:
- Find the single most common GPS coordinate across all photos
- Likely home if 20%+ of photos within 100m radius
- Offer "privacy mode" to exclude these from screensaver

### Implementation
```python
def detect_home_location(photos_with_gps, threshold=0.2):
    """
    Find location where most photos were taken (likely home)
    """
    # Cluster photos by location (100m radius)
    clusters = cluster_by_location(photos_with_gps, radius_m=100)
    
    # Find largest cluster
    largest_cluster = max(clusters, key=len)
    
    if len(largest_cluster) / len(photos_with_gps) >= threshold:
        centroid = calculate_centroid(largest_cluster)
        return {
            'latitude': centroid[0],
            'longitude': centroid[1],
            'num_photos': len(largest_cluster),
            'percentage': len(largest_cluster) / len(photos_with_gps),
            'label': 'Likely home location'
        }
    
    return None
```

## Testing Strategy

### Test Cases
1. **Vacation sequence**: 50 photos over 5 days, some with GPS
2. **Daily mix**: Photos from home and work, mixed GPS coverage
3. **Event photos**: Wedding/party photos from single location
4. **Travel photos**: Road trip with changing locations
5. **Screenshots**: Should NOT inherit location from nearby photos

### Success Metrics
- **Coverage**: % of missing photos successfully geotagged
- **Accuracy**: Manual spot-check of 50 random inferences
- **Confidence calibration**: Do 80% confidence predictions match 80% of time?

## Next Steps

1. Implement temporal clustering algorithm
2. Create batch processing script
3. Build approval UI in web interface
4. Test on your 479 missing photos
5. Iterate based on results

Would you like me to start implementing the temporal clustering algorithm?
