#!/usr/bin/env python3
"""
ABOUTME: Test script to validate speed adjustment for realistic urban cycling times
ABOUTME: Compares OSRM raw times vs adjusted times vs Google Maps expectations
"""


def test_speed_adjustments():
    """Test different speed adjustment factors."""

    # Test data: OSRM results vs Google Maps estimates
    test_routes = [
        {
            "name": "Paddington to Baker Street",
            "osrm_minutes": 5.1,
            "osrm_distance_km": 1.90,
            "google_minutes": 10,
        },
        {
            "name": "Hyde Park Corner to Kings Cross",
            "osrm_minutes": 13.7,
            "osrm_distance_km": 5.03,
            "google_minutes": 27,
        },
    ]

    print("=== SPEED ADJUSTMENT ANALYSIS ===")
    print()

    for route in test_routes:
        print(f"Route: {route['name']}")
        print(f"Distance: {route['osrm_distance_km']:.2f} km")
        print()

        # Calculate speeds
        osrm_speed = route["osrm_distance_km"] / (route["osrm_minutes"] / 60)
        google_speed = route["osrm_distance_km"] / (route["google_minutes"] / 60)

        print(f"OSRM: {route['osrm_minutes']:.1f} min → {osrm_speed:.1f} km/h")
        print(f"Google: {route['google_minutes']:.1f} min → {google_speed:.1f} km/h")

        # Calculate adjustment factor
        adjustment_factor = route["google_minutes"] / route["osrm_minutes"]
        print(f"Adjustment factor: {adjustment_factor:.2f}x")
        print()

    # Calculate average adjustment factor
    adjustments = []
    for route in test_routes:
        factor = route["google_minutes"] / route["osrm_minutes"]
        adjustments.append(factor)

    avg_adjustment = sum(adjustments) / len(adjustments)
    print(f"Average adjustment factor: {avg_adjustment:.2f}x")
    print()

    # Test with adjustment
    print("=== ADJUSTED TIMES ===")
    for route in test_routes:
        adjusted_time = route["osrm_minutes"] * avg_adjustment
        print(f"{route['name']}:")
        print(f"  OSRM raw: {route['osrm_minutes']:.1f} min")
        print(f"  Adjusted: {adjusted_time:.1f} min")
        print(f"  Google: {route['google_minutes']:.1f} min")
        print(f"  Error: {abs(adjusted_time - route['google_minutes']):.1f} min")
        print()


if __name__ == "__main__":
    test_speed_adjustments()
