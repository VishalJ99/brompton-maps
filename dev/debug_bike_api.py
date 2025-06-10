#!/usr/bin/env python3
"""
ABOUTME: Debug script to compare multiple bike routing APIs
ABOUTME: Tests OSRM, GraphHopper, and other APIs to compare timing estimates
"""

import argparse
import json
import os
import sys

import requests
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


def debug_osrm(start_lat, start_lng, end_lat, end_lng, target_speed_kmh=15.0):
    """Test OSRM bike routing API with speed scaling."""
    print("=== OSRM API (with speed scaling) ===")

    url = f"http://router.project-osrm.org/route/v1/cycling/{start_lng},{start_lat};{end_lng},{end_lat}"
    params = {"overview": "false", "steps": "false", "geometries": "geojson"}

    print(f"URL: {url}")
    print(f"Params: {params}")
    print(f"Target Speed: {target_speed_kmh} km/h")

    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            if data.get("code") == "Ok" and "routes" in data:
                route = data["routes"][0]
                duration_seconds = route.get("duration", 0)
                distance_meters = route.get("distance", 0)

                distance_km = distance_meters / 1000

                # Original OSRM timing
                osrm_duration_minutes = duration_seconds / 60
                osrm_speed_kmh = (
                    (distance_km / (osrm_duration_minutes / 60)) if osrm_duration_minutes > 0 else 0
                )

                # Scaled timing based on target speed
                scaled_duration_minutes = (distance_km / target_speed_kmh) * 60

                print(f"✅ Distance: {distance_km:.2f} km")
                print(
                    f"✅ OSRM Original: {osrm_duration_minutes:.1f} min ({osrm_speed_kmh:.1f} km/h)"
                )
                print(
                    f"✅ Scaled Duration: {scaled_duration_minutes:.1f} min ({target_speed_kmh:.1f} km/h)"
                )
                return scaled_duration_minutes, distance_km
            else:
                print(f"❌ API Error: {data.get('message', 'Unknown error')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")

    except Exception as e:
        print(f"❌ Request failed: {e}")

    return None, None


def debug_graphhopper(start_lat, start_lng, end_lat, end_lng):
    """Test GraphHopper bike routing API."""
    print("=== GRAPHHOPPER API ===")

    # Get API key from environment
    api_key = os.getenv("GRAPHHOPPER_API_KEY")
    if not api_key:
        print("❌ No API key found. Set GRAPHHOPPER_API_KEY in .env file")
        return None, None

    url = "https://graphhopper.com/api/1/route"
    params = {
        "point": [f"{start_lat},{start_lng}", f"{end_lat},{end_lng}"],
        "vehicle": "bike",
        "locale": "en",
        "calc_points": "false",
        "debug": "false",
        "elevation": "false",
        "points_encoded": "false",
        "key": api_key,
    }

    print(f"URL: {url}")
    print(f"Params: {params}")

    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            if "paths" in data and len(data["paths"]) > 0:
                path = data["paths"][0]
                duration_ms = path.get("time", 0)
                distance_meters = path.get("distance", 0)

                duration_minutes = duration_ms / (1000 * 60)
                distance_km = distance_meters / 1000
                avg_speed_kmh = (
                    (distance_km / (duration_minutes / 60)) if duration_minutes > 0 else 0
                )

                print(f"✅ Duration: {duration_minutes:.1f} minutes")
                print(f"✅ Distance: {distance_km:.2f} km")
                print(f"✅ Speed: {avg_speed_kmh:.1f} km/h")
                return duration_minutes, distance_km
            else:
                print(f"❌ API Error: {data.get('message', 'No paths found')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            if response.text:
                print(f"Response: {response.text[:200]}...")

    except Exception as e:
        print(f"❌ Request failed: {e}")

    return None, None


def compare_apis(start_lat, start_lng, end_lat, end_lng, api_name=None, target_speed_kmh=15.0):
    """Compare OSRM and GraphHopper bike routing APIs."""
    print("=== BIKE ROUTING API COMPARISON ===")
    print(f"From: ({start_lat}, {start_lng})")
    print(f"To: ({end_lat}, {end_lng})")
    print()

    results = {}

    if api_name is None or api_name == "osrm":
        duration, distance = debug_osrm(start_lat, start_lng, end_lat, end_lng, target_speed_kmh)
        if duration is not None:
            results["OSRM Scaled"] = {"duration": duration, "distance": distance}
        print()

    if api_name is None or api_name == "graphhopper":
        duration, distance = debug_graphhopper(start_lat, start_lng, end_lat, end_lng)
        if duration is not None:
            results["GraphHopper"] = {"duration": duration, "distance": distance}
        print()

    # Summary comparison
    if len(results) > 1:
        print("=== COMPARISON SUMMARY ===")
        for api, data in results.items():
            speed = (data["distance"] / (data["duration"] / 60)) if data["duration"] > 0 else 0
            print(
                f"{api:15}: {data['duration']:5.1f} min, {data['distance']:5.2f} km, {speed:5.1f} km/h"
            )

        # Calculate differences
        durations = [data["duration"] for data in results.values()]
        min_duration = min(durations)
        max_duration = max(durations)

        print()
        print(f"Duration range: {min_duration:.1f} - {max_duration:.1f} minutes")
        print(
            f"Max difference: {max_duration - min_duration:.1f} minutes ({((max_duration / min_duration - 1) * 100):.0f}%)"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare bike routing APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test all APIs - Paddington to Baker Street
  python debug_bike_api.py 51.5154 -0.1759 51.5226 -0.1574

  # Test only OSRM
  python debug_bike_api.py 51.5154 -0.1759 51.5226 -0.1574 --api osrm

  # Test only GraphHopper
  python debug_bike_api.py 51.5154 -0.1759 51.5226 -0.1574 --api graphhopper
        """,
    )

    parser.add_argument("start_lat", type=float, help="Starting latitude")
    parser.add_argument("start_lng", type=float, help="Starting longitude")
    parser.add_argument("end_lat", type=float, help="Ending latitude")
    parser.add_argument("end_lng", type=float, help="Ending longitude")
    parser.add_argument("--api", choices=["osrm", "graphhopper"], help="Test specific API only")
    parser.add_argument(
        "--speed", type=float, default=15.0, help="Target cycling speed in km/h (default: 15.0)"
    )

    args = parser.parse_args()

    compare_apis(args.start_lat, args.start_lng, args.end_lat, args.end_lng, args.api, args.speed)
