#!/usr/bin/env python3
"""
Audit geotag data in photo library
Scans all images and reports on GPS EXIF data coverage
"""

import os
import sys
from pathlib import Path
from collections import defaultdict
import json

def parse_gps_coordinate(ref, degrees, minutes, seconds):
    """Convert GPS coordinate from degrees/minutes/seconds to decimal"""
    decimal = float(degrees) + float(minutes)/60 + float(seconds)/3600
    if ref in ['S', 'W']:
        decimal = -decimal
    return decimal

def extract_gps_from_exif(image_path):
    """Extract GPS coordinates from image EXIF data"""
    try:
        # Try with Pillow first
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS

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
            return {'incomplete': True, 'data': gps_data}

        # Convert to decimal degrees
        lat = parse_gps_coordinate(
            gps_data.get('GPSLatitudeRef', 'N'),
            gps_data['GPSLatitude'][0],
            gps_data['GPSLatitude'][1],
            gps_data['GPSLatitude'][2]
        )

        lon = parse_gps_coordinate(
            gps_data.get('GPSLongitudeRef', 'E'),
            gps_data['GPSLongitude'][0],
            gps_data['GPSLongitude'][1],
            gps_data['GPSLongitude'][2]
        )

        return {
            'latitude': lat,
            'longitude': lon,
            'raw': gps_data
        }

    except ImportError:
        # Pillow not available, return None
        return None
    except Exception as e:
        return {'error': str(e)}

def audit_directory(directory_path):
    """Scan all images in directory and report on geotag coverage"""

    stats = {
        'total_images': 0,
        'has_complete_gps': 0,
        'has_incomplete_gps': 0,
        'has_no_gps': 0,
        'has_error': 0,
        'pillow_unavailable': False
    }

    samples = {
        'complete': [],
        'incomplete': [],
        'missing': [],
        'errors': []
    }

    image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}

    print(f"Scanning {directory_path}...")
    print()

    for filename in sorted(os.listdir(directory_path)):
        file_path = os.path.join(directory_path, filename)

        if not os.path.isfile(file_path):
            continue

        ext = os.path.splitext(filename)[1].lower()
        if ext not in image_extensions:
            continue

        stats['total_images'] += 1

        if stats['total_images'] % 100 == 0:
            print(f"Processed {stats['total_images']} images...", end='\r')

        gps_data = extract_gps_from_exif(file_path)

        if gps_data is None:
            stats['has_no_gps'] += 1
            if len(samples['missing']) < 5:
                samples['missing'].append(filename)
        elif 'error' in gps_data:
            stats['has_error'] += 1
            if len(samples['errors']) < 5:
                samples['errors'].append({'file': filename, 'error': gps_data['error']})
        elif 'incomplete' in gps_data:
            stats['has_incomplete_gps'] += 1
            if len(samples['incomplete']) < 5:
                samples['incomplete'].append({'file': filename, 'fields': list(gps_data['data'].keys())})
        else:
            stats['has_complete_gps'] += 1
            if len(samples['complete']) < 5:
                samples['complete'].append({
                    'file': filename,
                    'lat': gps_data['latitude'],
                    'lon': gps_data['longitude']
                })

    print()
    return stats, samples

def main():
    if len(sys.argv) > 1:
        photo_dir = sys.argv[1]
    else:
        photo_dir = '/export/ciriolisaver'

    if not os.path.isdir(photo_dir):
        print(f"Error: Directory not found: {photo_dir}")
        sys.exit(1)

    # Check if Pillow is available
    try:
        import PIL
        print("✓ Pillow library available")
        print()
    except ImportError:
        print("✗ Pillow library NOT available - cannot read EXIF data")
        print("  Install with: pip3 install Pillow")
        sys.exit(1)

    stats, samples = audit_directory(photo_dir)

    # Print report
    print("=" * 70)
    print("GEOTAG AUDIT REPORT")
    print("=" * 70)
    print()
    print(f"Total images scanned: {stats['total_images']}")
    print()
    print(f"✓ Complete GPS data:  {stats['has_complete_gps']:4d} ({stats['has_complete_gps']/stats['total_images']*100:5.1f}%)")
    print(f"⚠ Incomplete GPS:     {stats['has_incomplete_gps']:4d} ({stats['has_incomplete_gps']/stats['total_images']*100:5.1f}%)")
    print(f"✗ No GPS data:        {stats['has_no_gps']:4d} ({stats['has_no_gps']/stats['total_images']*100:5.1f}%)")
    print(f"⚠ Errors:             {stats['has_error']:4d} ({stats['has_error']/stats['total_images']*100:5.1f}%)")
    print()

    if samples['complete']:
        print("Sample images with complete GPS:")
        for s in samples['complete']:
            print(f"  • {s['file']}: {s['lat']:.6f}, {s['lon']:.6f}")
        print()

    if samples['incomplete']:
        print("Sample images with incomplete GPS:")
        for s in samples['incomplete']:
            print(f"  • {s['file']}: fields={', '.join(s['fields'])}")
        print()

    if samples['missing']:
        print("Sample images missing GPS:")
        for f in samples['missing']:
            print(f"  • {f}")
        print()

    if samples['errors']:
        print("Sample images with errors:")
        for s in samples['errors']:
            print(f"  • {s['file']}: {s['error']}")
        print()

    # Save detailed report
    report_file = os.path.join(os.path.dirname(__file__), 'geotag_audit_report.json')
    with open(report_file, 'w') as f:
        json.dump({
            'directory': photo_dir,
            'stats': stats,
            'samples': samples
        }, f, indent=2)

    print(f"Detailed report saved to: {report_file}")
    print()

if __name__ == '__main__':
    main()
