#!/usr/bin/env python3
"""
ABOUTME: CLI tool to get cycling time between two coordinates using OSRM
ABOUTME: Usage: python get_bike_time.py <start_lat> <start_lng> <end_lat> <end_lng>
"""

import argparse
import json
import sys
from typing import NamedTuple, Optional, Tuple

import requests


class BikeRouteResult(NamedTuple):
    """Result of a bike routing query."""

    duration_seconds: int
    distance_meters: int
    success: bool
    error_message: str | None = None


def get_bike_route_osrm(
    start_coords: tuple[float, float], end_coords: tuple[float, float]
) -> BikeRouteResult:
    """
    Get bike routing information between two coordinates using OSRM.

    Args:
        start_coords: (longitude, latitude) of start point
        end_coords: (longitude, latitude) of end point

    Returns:
        BikeRouteResult with duration, distance, and success status
    """
    start_lng, start_lat = start_coords
    end_lng, end_lat = end_coords

    # OSRM demo server endpoint for cycling
    url = f"http://router.project-osrm.org/route/v1/cycling/{start_lng},{start_lat};{end_lng},{end_lat}"
    params = {
        "overview": "false",  # We don't need the full geometry
        "steps": "false",  # We don't need turn-by-turn directions
        "geometries": "geojson",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data.get("code") != "Ok":
            return BikeRouteResult(
                0, 0, False, f"OSRM error: {data.get('message', 'Unknown error')}"
            )

        # Extract route information
        routes = data.get("routes", [])
        if not routes:
            return BikeRouteResult(0, 0, False, "No routes found")

        route = routes[0]  # Take the first (best) route
        duration_seconds = int(route.get("duration", 0))
        distance_meters = int(route.get("distance", 0))

        return BikeRouteResult(duration_seconds, distance_meters, True)

    except requests.exceptions.RequestException as e:
        return BikeRouteResult(0, 0, False, f"Network error: {e!s}")
    except json.JSONDecodeError as e:
        return BikeRouteResult(0, 0, False, f"JSON decode error: {e!s}")
    except Exception as e:
        return BikeRouteResult(0, 0, False, f"Unexpected error: {e!s}")


def main():
    parser = argparse.ArgumentParser(
        description="Get cycling time between two coordinates using OSRM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Paddington to Baker Street
  python get_bike_time.py 51.5154 -0.1759 51.5226 -0.1574

  # Hyde Park Corner to Kings Cross
  python get_bike_time.py 51.5028 -0.1527 51.5308 -0.1239
        """,
    )

    parser.add_argument("start_lat", type=float, help="Starting latitude")
    parser.add_argument("start_lng", type=float, help="Starting longitude")
    parser.add_argument("end_lat", type=float, help="Ending latitude")
    parser.add_argument("end_lng", type=float, help="Ending longitude")
    parser.add_argument(
        "--speed", type=float, default=15.0, help="Target cycling speed in km/h (default: 15.0)"
    )
    parser.add_argument("--json", action="store_true", help="Output result as JSON")

    args = parser.parse_args()

    # Get bike route
    start_coords = (args.start_lng, args.start_lat)  # OSRM expects (lng, lat)
    end_coords = (args.end_lng, args.end_lat)

    print(
        f"Calculating bike route from ({args.start_lat:.4f}, {args.start_lng:.4f}) to ({args.end_lat:.4f}, {args.end_lng:.4f})..."
    )

    result = get_bike_route_osrm(start_coords, end_coords)

    if args.json:
        # JSON output for programmatic use
        output = {
            "success": result.success,
            "duration_seconds": result.duration_seconds,
            "duration_minutes": round(result.duration_seconds / 60, 1),
            "distance_meters": result.distance_meters,
            "distance_km": round(result.distance_meters / 1000, 2),
            "error_message": result.error_message,
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        if result.success:
            duration_min = result.duration_seconds / 60
            distance_km = result.distance_meters / 1000
            avg_speed_kmh = (distance_km / (duration_min / 60)) if duration_min > 0 else 0

            print("✅ Bike route found:")
            print(f"  Duration: {duration_min:.1f} minutes")
            print(f"  Distance: {distance_km:.2f} km")
            print(f"  Average speed: {avg_speed_kmh:.1f} km/h")
        else:
            print(f"❌ Failed to get bike route: {result.error_message}")
            sys.exit(1)


if __name__ == "__main__":
    main()
