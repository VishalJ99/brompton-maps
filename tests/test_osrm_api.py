#!/usr/bin/env python3
"""
ABOUTME: Test script for OSRM cycling API to validate bike routing functionality
ABOUTME: Tests coordinate-to-coordinate cycling time estimation for London locations
"""

import json
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


def test_london_bike_routes():
    """Test bike routing with some known London locations."""
    print("Testing OSRM Cycling API with London coordinates...")
    print("=" * 60)

    # Test coordinates (longitude, latitude)
    test_cases = [
        {
            "name": "Short ride: Paddington to Baker Street",
            "start": (-0.1759, 51.5154),  # Paddington Station
            "end": (-0.1574, 51.5226),  # Baker Street Station
            "expected_duration_min": "5-10",
        },
        {
            "name": "Medium ride: Hyde Park Corner to Kings Cross",
            "start": (-0.1527, 51.5028),  # Hyde Park Corner
            "end": (-0.1239, 51.5308),  # Kings Cross
            "expected_duration_min": "15-25",
        },
        {
            "name": "Longer ride: Greenwich to Westminster",
            "start": (-0.0050, 51.4779),  # Greenwich
            "end": (-0.1248, 51.4994),  # Westminster
            "expected_duration_min": "30-45",
        },
    ]

    for test in test_cases:
        print(f"\n{test['name']}")
        print(f"Expected cycling time: {test['expected_duration_min']} minutes")

        result = get_bike_route_osrm(test["start"], test["end"])

        if result.success:
            duration_min = result.duration_seconds / 60
            distance_km = result.distance_meters / 1000
            avg_speed_kmh = (distance_km / (duration_min / 60)) if duration_min > 0 else 0

            print("✅ SUCCESS:")
            print(f"  Duration: {duration_min:.1f} minutes")
            print(f"  Distance: {distance_km:.2f} km")
            print(f"  Average speed: {avg_speed_kmh:.1f} km/h")
        else:
            print(f"❌ FAILED: {result.error_message}")


if __name__ == "__main__":
    test_london_bike_routes()
