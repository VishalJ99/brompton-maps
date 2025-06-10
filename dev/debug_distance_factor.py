#!/usr/bin/env python3
"""
ABOUTME: Debug script to analyze straight-line distance vs OSRM routing time conversion factors
ABOUTME: Helps optimize the filtering threshold for virtual node creation in multi-layer routing
"""

import argparse
import json
import math
import random
import statistics
import sys
import time
from typing import Dict, List, Optional, Tuple

from bike_routing import create_osrm_router


class DistanceFactorAnalyzer:
    """Analyze conversion factors between straight-line and actual routing metrics."""

    def __init__(self, cycle_speed_kmh: float = 15.0):
        """
        Initialize analyzer with bike router.

        Args:
            cycle_speed_kmh: Cycling speed for time calculations
        """
        self.cycle_speed_kmh = cycle_speed_kmh
        self.bike_router = create_osrm_router(cycle_speed_kmh)
        self.stations_data = self._load_stations()

    def _load_stations(self) -> dict | None:
        """Load TfL stations data for batch testing."""
        try:
            with open("tfl_stations.json") as f:
                data = json.load(f)
                return data.get("stations", {})
        except FileNotFoundError:
            print("⚠️  TfL stations file not found - batch testing will be limited")
            return None

    def _calculate_haversine_distance(
        self, coord1: tuple[float, float], coord2: tuple[float, float]
    ) -> float:
        """Calculate straight-line distance in kilometers."""
        lon1, lat1 = coord1
        lon2, lat2 = coord2

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))

        # Earth's radius in kilometers
        return 6371 * c

    def _calculate_straight_line_time(self, distance_km: float) -> float:
        """Calculate straight-line cycling time in minutes."""
        return (distance_km / self.cycle_speed_kmh) * 60

    def analyze_single_route(
        self,
        start_coords: tuple[float, float],
        end_coords: tuple[float, float],
        show_details: bool = True,
    ) -> dict:
        """
        Analyze a single route pair.

        Args:
            start_coords: (longitude, latitude) of start
            end_coords: (longitude, latitude) of end
            show_details: Whether to print detailed output

        Returns:
            Analysis results dictionary
        """
        # Calculate straight-line metrics
        straight_distance_km = self._calculate_haversine_distance(start_coords, end_coords)
        straight_time_min = self._calculate_straight_line_time(straight_distance_km)

        # Get OSRM routing
        osrm_result = self.bike_router.get_route(start_coords, end_coords)

        if not osrm_result.success:
            if show_details:
                print(f"❌ OSRM routing failed: {osrm_result.error_message}")
            return None

        # Calculate conversion factors
        distance_factor = (
            osrm_result.distance_km / straight_distance_km if straight_distance_km > 0 else 0
        )
        time_factor = (
            osrm_result.duration_minutes / straight_time_min if straight_time_min > 0 else 0
        )
        route_efficiency = (
            straight_distance_km / osrm_result.distance_km if osrm_result.distance_km > 0 else 0
        )

        # Test different filter thresholds
        current_2x_threshold = straight_time_min * 2
        current_15x_threshold = straight_time_min * 1.5
        current_13x_threshold = straight_time_min * 1.3

        filter_results = {
            "2.0x": osrm_result.duration_minutes <= current_2x_threshold,
            "1.5x": osrm_result.duration_minutes <= current_15x_threshold,
            "1.3x": osrm_result.duration_minutes <= current_13x_threshold,
        }

        results = {
            "start_coords": start_coords,
            "end_coords": end_coords,
            "straight_distance_km": straight_distance_km,
            "straight_time_min": straight_time_min,
            "osrm_distance_km": osrm_result.distance_km,
            "osrm_time_min": osrm_result.duration_minutes,
            "distance_factor": distance_factor,
            "time_factor": time_factor,
            "route_efficiency": route_efficiency,
            "filter_results": filter_results,
        }

        if show_details:
            self._print_single_analysis(results)

        return results

    def _print_single_analysis(self, results: dict):
        """Print detailed analysis for a single route."""
        print(f"\n{'=' * 60}")
        print("🗺️  DISTANCE vs OSRM TIME ANALYSIS")
        print(f"{'=' * 60}")
        print(f"Route: {results['start_coords']} → {results['end_coords']}")
        print()

        print("📏 Straight-line Analysis:")
        print(f"├─ Distance: {results['straight_distance_km']:.2f} km")
        print(f"├─ Time @ {self.cycle_speed_kmh} km/h: {results['straight_time_min']:.1f} minutes")
        print(f"└─ Current 2x filter allows: {results['straight_time_min'] * 2:.1f} min routes")
        print()

        print("🚴 OSRM Actual Results:")
        print(
            f"├─ Distance: {results['osrm_distance_km']:.2f} km ({results['distance_factor']:.2f}x factor)"
        )
        print(
            f"├─ Time: {results['osrm_time_min']:.1f} minutes ({results['time_factor']:.2f}x factor)"
        )
        print(f"└─ Route efficiency: {results['route_efficiency']:.1%}")
        print()

        print("🎯 Filtering Analysis:")
        for factor, passes in results["filter_results"].items():
            status = "✅" if passes else "❌"
            print(f"├─ {factor} factor catches this route: {status}")
        print(f"└─ Recommended factor: {max(1.1, results['time_factor'] * 1.1):.1f}x")
        print()

    def batch_analysis(self, num_routes: int = 50, max_distance_km: float = 20.0) -> dict:
        """
        Perform batch analysis on multiple routes.

        Args:
            num_routes: Number of route pairs to test
            max_distance_km: Maximum straight-line distance to test

        Returns:
            Batch analysis results
        """
        print(f"\n🔍 Running batch analysis on {num_routes} routes...")
        print(f"   Max distance: {max_distance_km} km")
        print(f"   Cycle speed: {self.cycle_speed_kmh} km/h")

        results = []
        london_bounds = {"min_lon": -0.5, "max_lon": 0.2, "min_lat": 51.3, "max_lat": 51.7}

        # Generate test routes
        for i in range(num_routes):
            if i % 10 == 0:
                print(f"   Progress: {i}/{num_routes}")

            # Generate random coordinates in London area
            start_coords = (
                random.uniform(london_bounds["min_lon"], london_bounds["max_lon"]),
                random.uniform(london_bounds["min_lat"], london_bounds["max_lat"]),
            )

            # Generate end coordinates within max_distance_km
            max_coord_delta = max_distance_km / 111.0  # Rough conversion to degrees
            end_coords = (
                start_coords[0] + random.uniform(-max_coord_delta, max_coord_delta),
                start_coords[1] + random.uniform(-max_coord_delta, max_coord_delta),
            )

            # Analyze this route
            result = self.analyze_single_route(start_coords, end_coords, show_details=False)
            if result:
                results.append(result)

            # Rate limiting - be nice to OSRM
            time.sleep(0.1)

        return self._summarize_batch_results(results)

    def station_based_analysis(self, num_routes: int = 30) -> dict:
        """
        Analyze routes from random points to actual TfL stations.

        Args:
            num_routes: Number of routes to test

        Returns:
            Analysis results
        """
        if not self.stations_data:
            print("❌ No station data available for station-based analysis")
            return {}

        print(f"\n🚇 Running station-based analysis on {num_routes} routes...")

        results = []
        stations_list = list(self.stations_data.values())
        london_bounds = {"min_lon": -0.5, "max_lon": 0.2, "min_lat": 51.3, "max_lat": 51.7}

        for i in range(num_routes):
            if i % 10 == 0:
                print(f"   Progress: {i}/{num_routes}")

            # Random start point in London
            start_coords = (
                random.uniform(london_bounds["min_lon"], london_bounds["max_lon"]),
                random.uniform(london_bounds["min_lat"], london_bounds["max_lat"]),
            )

            # Random TfL station as destination
            station = random.choice(stations_list)
            end_coords = (station["lon"], station["lat"])

            # Analyze this route
            result = self.analyze_single_route(start_coords, end_coords, show_details=False)
            if result:
                results.append(result)

            # Rate limiting
            time.sleep(0.1)

        return self._summarize_batch_results(results, "Station-based")

    def _summarize_batch_results(self, results: list[dict], analysis_type: str = "Batch") -> dict:
        """Summarize batch analysis results."""
        if not results:
            print("❌ No successful routes to analyze")
            return {}

        # Extract metrics
        distance_factors = [r["distance_factor"] for r in results]
        time_factors = [r["time_factor"] for r in results]
        route_efficiencies = [r["route_efficiency"] for r in results]

        # Filter threshold analysis
        filter_stats = {}
        for factor in ["2.0x", "1.5x", "1.3x"]:
            passes = sum(1 for r in results if r["filter_results"][factor])
            filter_stats[factor] = {"passes": passes, "percentage": passes / len(results) * 100}

        summary = {
            "total_routes": len(results),
            "distance_factor_stats": {
                "mean": statistics.mean(distance_factors),
                "median": statistics.median(distance_factors),
                "min": min(distance_factors),
                "max": max(distance_factors),
                "std": statistics.stdev(distance_factors) if len(distance_factors) > 1 else 0,
            },
            "time_factor_stats": {
                "mean": statistics.mean(time_factors),
                "median": statistics.median(time_factors),
                "min": min(time_factors),
                "max": max(time_factors),
                "std": statistics.stdev(time_factors) if len(time_factors) > 1 else 0,
            },
            "route_efficiency_stats": {
                "mean": statistics.mean(route_efficiencies),
                "median": statistics.median(route_efficiencies),
                "min": min(route_efficiencies),
                "max": max(route_efficiencies),
            },
            "filter_analysis": filter_stats,
        }

        self._print_batch_summary(summary, analysis_type)
        return summary

    def _print_batch_summary(self, summary: dict, analysis_type: str):
        """Print batch analysis summary."""
        print(f"\n{'=' * 60}")
        print(f"📊 {analysis_type.upper()} ANALYSIS SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total routes analyzed: {summary['total_routes']}")
        print()

        print("📏 Distance Factor Analysis:")
        ds = summary["distance_factor_stats"]
        print(f"├─ Mean: {ds['mean']:.2f}x")
        print(f"├─ Median: {ds['median']:.2f}x")
        print(f"├─ Range: {ds['min']:.2f}x - {ds['max']:.2f}x")
        print(f"└─ Std Dev: {ds['std']:.2f}")
        print()

        print("⏱️  Time Factor Analysis:")
        ts = summary["time_factor_stats"]
        print(f"├─ Mean: {ts['mean']:.2f}x")
        print(f"├─ Median: {ts['median']:.2f}x")
        print(f"├─ Range: {ts['min']:.2f}x - {ts['max']:.2f}x")
        print(f"└─ Std Dev: {ts['std']:.2f}")
        print()

        print("🎯 Filter Threshold Analysis:")
        for factor, stats in summary["filter_analysis"].items():
            print(
                f"├─ {factor} factor catches: {stats['passes']}/{summary['total_routes']} routes ({stats['percentage']:.1f}%)"
            )
        print()

        # Recommendations
        recommended_factor = ts["median"] * 1.2  # 20% buffer above median
        print("💡 RECOMMENDATIONS:")
        print(
            f"├─ Current 2.0x factor: {'Conservative' if recommended_factor < 2.0 else 'Appropriate'}"
        )
        print(f"├─ Recommended factor: {recommended_factor:.1f}x")
        print(
            f"├─ This would catch ~{self._estimate_catch_rate(summary['time_factor_stats'], recommended_factor):.0f}% of routes"
        )
        print(f"└─ Potential API call reduction: {((2.0 - recommended_factor) / 2.0 * 100):.0f}%")
        print()

    def _estimate_catch_rate(self, time_stats: dict, factor: float) -> float:
        """Estimate what percentage of routes a given factor would catch."""
        # Rough estimation assuming normal distribution
        mean = time_stats["mean"]
        std = time_stats["std"]

        if std == 0:
            return 100.0 if factor >= mean else 0.0

        # Simple heuristic - not perfectly accurate but good enough for estimation
        z_score = (factor - mean) / std
        if z_score >= 2:
            return 97.5
        elif z_score >= 1:
            return 84.1
        elif z_score >= 0:
            return 50.0 + (z_score / 2) * 34.1
        else:
            return 50.0 + (z_score / 2) * 34.1


def main():
    """Command-line interface for distance factor analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze straight-line vs OSRM routing conversion factors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze single route
  python debug_distance_factor.py single -0.1278 51.5074 -0.0772 51.5031

  # Batch analysis with 50 random routes
  python debug_distance_factor.py batch --num-routes 50

  # Station-based analysis
  python debug_distance_factor.py stations --num-routes 30

  # Custom cycling speed
  python debug_distance_factor.py single -0.1278 51.5074 -0.0772 51.5031 --speed 12
        """,
    )

    parser.add_argument(
        "--speed", type=float, default=15.0, help="Cycling speed in km/h (default: 15.0)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Analysis mode")

    # Single route analysis
    single_parser = subparsers.add_parser("single", help="Analyze a single route")
    single_parser.add_argument("start_lon", type=float, help="Start longitude")
    single_parser.add_argument("start_lat", type=float, help="Start latitude")
    single_parser.add_argument("end_lon", type=float, help="End longitude")
    single_parser.add_argument("end_lat", type=float, help="End latitude")

    # Batch analysis
    batch_parser = subparsers.add_parser("batch", help="Batch analysis with random routes")
    batch_parser.add_argument("--num-routes", type=int, default=50, help="Number of routes to test")
    batch_parser.add_argument("--max-distance", type=float, default=20.0, help="Max distance in km")

    # Station-based analysis
    station_parser = subparsers.add_parser("stations", help="Analysis using TfL stations")
    station_parser.add_argument(
        "--num-routes", type=int, default=30, help="Number of routes to test"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Create analyzer
    analyzer = DistanceFactorAnalyzer(cycle_speed_kmh=args.speed)

    if args.command == "single":
        start_coords = (args.start_lon, args.start_lat)
        end_coords = (args.end_lon, args.end_lat)
        analyzer.analyze_single_route(start_coords, end_coords)

    elif args.command == "batch":
        analyzer.batch_analysis(num_routes=args.num_routes, max_distance_km=args.max_distance)

    elif args.command == "stations":
        analyzer.station_based_analysis(num_routes=args.num_routes)


if __name__ == "__main__":
    main()
