#!/usr/bin/env python3
"""
ABOUTME: Main routing engine for optimal bike+tube journey planning using Dijkstra's algorithm
ABOUTME: Accepts start/end coordinates and finds best multi-modal route through London
"""

import argparse
import math
import pickle
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import networkx as nx

from bike_routing import create_osrm_router
from routing_config import (
    DEFAULT_CYCLE_SPEED_KMH,
    apply_journey_buffers,
    get_transport_emoji,
    validate_cycle_speed,
)
from routing_utils import (
    calculate_total_duration,
    extract_path_segments,
    format_detailed_journey,
    format_journey_summary,
    format_simple_journey,
    group_journey_legs,
)


class BikeTransitRouter:
    """Main routing engine for bike+transit journey planning."""

    def __init__(
        self,
        graph_file: str = "merged_graph.pickle",
        cycle_speed_kmh: float = DEFAULT_CYCLE_SPEED_KMH,
    ):
        """
        Initialize router with merged graph and configuration.

        Args:
            graph_file: Path to merged graph pickle file
            cycle_speed_kmh: Cycling speed in km/h
        """
        self.cycle_speed_kmh = validate_cycle_speed(cycle_speed_kmh)
        self.graph = self._load_graph(graph_file)
        self.bike_router = create_osrm_router(self.cycle_speed_kmh)

    def _load_graph(self, graph_file: str) -> nx.Graph:
        """Load merged graph from pickle file."""
        print(f"Loading routing graph from {graph_file}...")

        try:
            with open(graph_file, "rb") as f:
                graph = pickle.load(f)

            print(
                f"✅ Loaded graph: {graph.number_of_nodes()} stations, {graph.number_of_edges()} connections"
            )
            return graph

        except FileNotFoundError:
            print(f"❌ Graph file not found: {graph_file}")
            print("   Run merge_graphs.py first to create the unified network")
            sys.exit(1)

    def _calculate_haversine_distance(
        self, coord1: tuple[float, float], coord2: tuple[float, float]
    ) -> float:
        """
        Calculate straight-line distance between two coordinates in kilometers.

        Args:
            coord1: (longitude, latitude) of first point
            coord2: (longitude, latitude) of second point

        Returns:
            Distance in kilometers
        """
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
        r = 6371

        return c * r

    def _add_virtual_nodes(
        self,
        start_coords: tuple[float, float],
        end_coords: tuple[float, float],
        max_bike_only_minutes: float = 45.0,
    ) -> nx.Graph:
        """
        Add virtual start/end nodes with bike connections to all stations.

        Args:
            start_coords: (longitude, latitude) of start point
            end_coords: (longitude, latitude) of end point

        Returns:
            Augmented graph with virtual nodes
        """
        # Create a copy to avoid modifying original graph
        augmented_graph = self.graph.copy()

        # Add virtual start node
        augmented_graph.add_node(
            "start", name="Start Location", lat=start_coords[1], lon=start_coords[0]
        )

        # Add virtual end node
        augmented_graph.add_node("end", name="End Location", lat=end_coords[1], lon=end_coords[0])

        # Calculate distance threshold based on max bike time and speed
        # Using 2x adjustment factor for actual vs straight-line distance
        max_straight_line_km = (max_bike_only_minutes * self.cycle_speed_kmh / 60) / 2.0

        print("\nCalculating bike routes from start location...")
        print(
            f"  🎯 Filtering stations within {max_straight_line_km:.1f} km straight-line distance"
        )
        print(
            f"  ⚡ Using {max_bike_only_minutes} min threshold at {self.cycle_speed_kmh} km/h with 2x factor"
        )

        start_time = time.time()
        edges_added = 0
        stations_filtered = 0

        # Filter stations by distance first
        stations_to_query = []
        for station_id, station_data in self.graph.nodes(data=True):
            station_coords = (station_data["lon"], station_data["lat"])
            distance_km = self._calculate_haversine_distance(start_coords, station_coords)

            if distance_km <= max_straight_line_km:
                stations_to_query.append((station_id, station_coords))
            else:
                stations_filtered += 1

        print(
            f"  📊 Querying {len(stations_to_query)} stations (filtered {stations_filtered} distant stations)"
        )

        # Add bike edges from start to filtered stations using parallel requests
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all route calculations
            futures = {}
            for station_id, station_coords in stations_to_query:
                future = executor.submit(self.bike_router.get_route, start_coords, station_coords)
                futures[future] = station_id

            # Process results as they complete
            for future in as_completed(futures):
                station_id = futures[future]
                try:
                    result = future.result()
                    if result.success and result.duration_minutes > 0:
                        augmented_graph.add_edge(
                            "start",
                            station_id,
                            duration_minutes=result.duration_minutes,
                            transport_mode="bike",
                            distance_km=result.distance_km,
                            line=None,
                        )
                        edges_added += 1
                except Exception as e:
                    print(f"  ⚠️  Error calculating route to station {station_id}: {e}")

        print(f"✅ Added {edges_added} bike routes from start ({time.time() - start_time:.1f}s)")

        print("\nCalculating bike routes to end location...")
        print(
            f"  🎯 Filtering stations within {max_straight_line_km:.1f} km straight-line distance"
        )

        start_time = time.time()
        edges_added = 0
        stations_filtered = 0

        # Filter stations by distance first
        stations_to_query = []
        for station_id, station_data in self.graph.nodes(data=True):
            station_coords = (station_data["lon"], station_data["lat"])
            distance_km = self._calculate_haversine_distance(station_coords, end_coords)

            if distance_km <= max_straight_line_km:
                stations_to_query.append((station_id, station_coords))
            else:
                stations_filtered += 1

        print(
            f"  📊 Querying {len(stations_to_query)} stations (filtered {stations_filtered} distant stations)"
        )

        # Add bike edges from filtered stations to end using parallel requests
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all route calculations
            futures = {}
            for station_id, station_coords in stations_to_query:
                future = executor.submit(self.bike_router.get_route, station_coords, end_coords)
                futures[future] = station_id

            # Process results as they complete
            for future in as_completed(futures):
                station_id = futures[future]
                try:
                    result = future.result()
                    if result.success and result.duration_minutes > 0:
                        augmented_graph.add_edge(
                            station_id,
                            "end",
                            duration_minutes=result.duration_minutes,
                            transport_mode="bike",
                            distance_km=result.distance_km,
                            line=None,
                        )
                        edges_added += 1
                except Exception as e:
                    print(f"  ⚠️  Error calculating route from station {station_id}: {e}")

        print(f"✅ Added {edges_added} bike routes to end ({time.time() - start_time:.1f}s)")

        return augmented_graph

    def find_optimal_route(
        self,
        start_coords: tuple[float, float],
        end_coords: tuple[float, float],
        max_bike_only_minutes: float = 45.0,
    ) -> dict | None:
        """
        Find optimal bike+tube route between two coordinates.

        Args:
            start_coords: (longitude, latitude) of start point
            end_coords: (longitude, latitude) of end point
            max_bike_only_minutes: Maximum time to consider bike-only route

        Returns:
            Route information dictionary or None if no route found
        """
        print(f"\n{get_transport_emoji('bike')} Finding optimal bike+tube route...")
        print(f"From: ({start_coords[1]:.4f}, {start_coords[0]:.4f})")
        print(f"To: ({end_coords[1]:.4f}, {end_coords[0]:.4f})")

        # First check if direct bike route is reasonable
        print("\nChecking direct bike route...")
        direct_bike = self.bike_router.get_route(start_coords, end_coords)

        if direct_bike.success:
            print(
                f"Direct bike: {direct_bike.duration_minutes:.1f} minutes, {direct_bike.distance_km:.1f} km"
            )

            if direct_bike.duration_minutes <= max_bike_only_minutes:
                print(
                    f"✅ Direct bike route is optimal (under {max_bike_only_minutes} min threshold)"
                )

                # Create minimal augmented graph for direct bike route
                direct_augmented = nx.Graph()
                direct_augmented.add_node(
                    "start", name="Start Location", lat=start_coords[1], lon=start_coords[0]
                )
                direct_augmented.add_node(
                    "end", name="End Location", lat=end_coords[1], lon=end_coords[0]
                )
                direct_augmented.add_edge(
                    "start",
                    "end",
                    duration_minutes=direct_bike.duration_minutes,
                    transport_mode="bike",
                    distance_km=direct_bike.distance_km,
                    line=None,
                )

                return {
                    "path": ["start", "end"],
                    "segments": [
                        (
                            "start",
                            "end",
                            {
                                "duration_minutes": direct_bike.duration_minutes,
                                "transport_mode": "bike",
                                "distance_km": direct_bike.distance_km,
                                "line": None,
                            },
                        )
                    ],
                    "total_duration": direct_bike.duration_minutes,
                    "is_direct_bike": True,
                    "augmented_graph": direct_augmented,
                }

        # Create augmented graph with virtual nodes
        print("\nBuilding augmented graph with bike connections...")
        augmented_graph = self._add_virtual_nodes(start_coords, end_coords, max_bike_only_minutes)

        # Run Dijkstra's algorithm
        print("\nRunning Dijkstra's algorithm...")
        try:
            # Find shortest path using duration as weight
            path = nx.shortest_path(
                augmented_graph, source="start", target="end", weight="duration_minutes"
            )

            # Extract path segments
            segments = extract_path_segments(augmented_graph, path)

            # Apply journey buffers
            adjusted_segments = apply_journey_buffers(segments)

            # Calculate total duration
            total_duration = calculate_total_duration(adjusted_segments)

            print(f"✅ Found optimal route: {len(path)} nodes, {total_duration:.1f} minutes total")

            return {
                "path": path,
                "segments": adjusted_segments,
                "total_duration": total_duration,
                "is_direct_bike": False,
                "augmented_graph": augmented_graph,
            }

        except nx.NetworkXNoPath:
            print("❌ No route found between start and end locations")
            return None
        except Exception as e:
            print(f"❌ Error finding route: {e}")
            return None

    def format_route(
        self,
        route_info: dict,
        output_format: str = "detailed",
        start_name: str = "Your location",
        end_name: str = "Your destination",
    ) -> str:
        """
        Format route information for display.

        Args:
            route_info: Route information from find_optimal_route
            output_format: 'detailed', 'summary', or 'simple'
            start_name: Name for start location
            end_name: Name for end location

        Returns:
            Formatted route string
        """
        if route_info["is_direct_bike"]:
            # Handle direct bike route
            duration = route_info["total_duration"]
            distance = route_info["segments"][0][2].get("distance_km", 0)

            lines = [
                f"\n{get_transport_emoji('bike')} Direct Bike Route",
                "=" * 50,
                f"Duration: {duration:.1f} minutes",
                f"Distance: {distance:.1f} km",
                f"Average speed: {self.cycle_speed_kmh:.1f} km/h",
            ]
            return "\n".join(lines)

        # Group journey legs using the augmented graph
        augmented_graph = route_info.get("augmented_graph", self.graph)
        legs = group_journey_legs(route_info["segments"], augmented_graph)

        if output_format == "simple":
            return format_simple_journey(legs, route_info["total_duration"])
        elif output_format == "summary":
            return format_journey_summary(legs, route_info["total_duration"], start_name, end_name)
        else:  # detailed
            summary = format_journey_summary(
                legs, route_info["total_duration"], start_name, end_name
            )
            details = format_detailed_journey(
                legs, route_info["total_duration"], start_name, end_name
            )
            return summary + "\n" + details


def main():
    parser = argparse.ArgumentParser(
        description="Find optimal bike+tube routes through London",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find route from Paddington to Imperial College
  python route_planner.py --start-lat 51.5154 --start-lng -0.1759 --end-lat 51.4994 --end-lng -0.1749

  # Use custom cycle speed (20 km/h)
  python route_planner.py --start-lat 51.5154 --start-lng -0.1759 --end-lat 51.4994 --end-lng -0.1749 --speed 20

  # Simple one-line output
  python route_planner.py --start-lat 51.5154 --start-lng -0.1759 --end-lat 51.4994 --end-lng -0.1749 --format simple
        """,
    )

    # Required arguments
    parser.add_argument("--start-lat", type=float, required=True, help="Starting latitude")
    parser.add_argument("--start-lng", type=float, required=True, help="Starting longitude")
    parser.add_argument("--end-lat", type=float, required=True, help="Ending latitude")
    parser.add_argument("--end-lng", type=float, required=True, help="Ending longitude")

    # Optional arguments
    parser.add_argument(
        "--speed",
        type=float,
        default=DEFAULT_CYCLE_SPEED_KMH,
        help=f"Cycling speed in km/h (default: {DEFAULT_CYCLE_SPEED_KMH})",
    )
    parser.add_argument(
        "--graph",
        default="merged_graph.pickle",
        help="Merged graph file (default: merged_graph.pickle)",
    )
    parser.add_argument(
        "--format",
        choices=["detailed", "summary", "simple"],
        default="detailed",
        help="Output format (default: detailed)",
    )
    parser.add_argument(
        "--max-bike",
        type=float,
        default=45.0,
        help="Maximum minutes to consider bike-only route (default: 45)",
    )
    parser.add_argument(
        "--start-name",
        default="Your location",
        help="Name for start location",
    )
    parser.add_argument(
        "--end-name",
        default="Your destination",
        help="Name for end location",
    )

    args = parser.parse_args()

    # Initialize router
    router = BikeTransitRouter(args.graph, args.speed)

    # Find optimal route
    start_coords = (args.start_lng, args.start_lat)
    end_coords = (args.end_lng, args.end_lat)

    route = router.find_optimal_route(start_coords, end_coords, args.max_bike)

    if route:
        # Format and display route
        formatted = router.format_route(route, args.format, args.start_name, args.end_name)
        print(formatted)
    else:
        print("\n❌ Unable to find a route. Please check your coordinates.")
        sys.exit(1)


if __name__ == "__main__":
    main()
