#!/usr/bin/env python3
"""
ABOUTME: Test if reversing direction fixes all Bond Street routing failures
ABOUTME: Checks all 28 failed routes by swapping origin/destination
"""

import json
import time

import requests


def test_osrm_route(from_lat, from_lon, to_lat, to_lon):
    """Test OSRM route and return duration or None if failed."""
    url = f"http://router.project-osrm.org/route/v1/cycling/{from_lon},{from_lat};{to_lon},{to_lat}"
    params = {"overview": "false", "steps": "false", "geometries": "geojson"}

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "Ok" and "routes" in data:
                route = data["routes"][0]
                duration_seconds = route.get("duration", 0)
                return duration_seconds / 60  # Convert to minutes
        return None
    except Exception:
        return None


def main():
    # Load progress data
    with open("bike_graph_progress.json") as f:
        progress_data = json.load(f)

    # Load station data
    with open("tfl_stations.json") as f:
        stations_data = json.load(f)
    stations = stations_data["stations"]

    # Find all failed routes (null values)
    failed_routes = [(k, v) for k, v in progress_data["bike_time_cache"].items() if v is None]
    print(f"Found {len(failed_routes)} failed routes to test\n")

    # Test each failed route in reverse
    successful_reversals = 0
    still_failed = 0

    for i, (key, _) in enumerate(failed_routes):
        station1_id, station2_id = key.split("|")
        station1 = stations[station1_id]
        station2 = stations[station2_id]

        print(f"[{i + 1}/{len(failed_routes)}] Testing: {station1['name']} ↔ {station2['name']}")

        # Test original direction (should fail)
        orig_duration = test_osrm_route(
            station1["lat"], station1["lon"], station2["lat"], station2["lon"]
        )

        # Test reverse direction
        reverse_duration = test_osrm_route(
            station2["lat"], station2["lon"], station1["lat"], station1["lon"]
        )

        print(
            f"  Original ({station1_id} → {station2_id}): {'FAILED' if orig_duration is None else f'{orig_duration:.1f} min'}"
        )
        print(
            f"  Reversed ({station2_id} → {station1_id}): {'FAILED' if reverse_duration is None else f'{reverse_duration:.1f} min'}"
        )

        if reverse_duration is not None:
            successful_reversals += 1
            print("  ✅ Reversal successful!")
        else:
            still_failed += 1
            print("  ❌ Reversal also failed")

        print()
        time.sleep(0.1)  # Rate limiting

    # Summary
    print("\n=== REVERSAL TEST SUMMARY ===")
    print(f"Total failed routes tested: {len(failed_routes)}")
    print(f"✅ Successful reversals: {successful_reversals}")
    print(f"❌ Still failed after reversal: {still_failed}")
    print(f"Success rate: {(successful_reversals / len(failed_routes) * 100):.1f}%")


if __name__ == "__main__":
    main()
