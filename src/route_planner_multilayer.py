#!/usr/bin/env python3
"""
ABOUTME: Multi-layer routing engine for optimal bike+tube journey planning with line change modeling
ABOUTME: Accepts start/end coordinates and finds best route considering line changes during pathfinding
"""

import argparse
import math
import pickle
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import networkx as nx

from bike_routing import create_google_maps_router
from routing_config import (
    DEFAULT_CYCLE_SPEED_KMH,
    LINE_CHANGE_TIME_MINUTES,
    STATION_ACCESS_TIME_MINUTES,
    TRAIN_WAITING_TIME_MINUTES,
    get_transport_emoji,
    validate_cycle_speed,
)
from routing_utils import (
    calculate_total_duration,
    format_journey_summary,
)


class MultiLayerBikeTransitRouter:
    """Multi-layer routing engine for bike+transit journey planning."""

    def __init__(
        self,
        graph_file: str = "data/merged_multilayer_graph.pickle",
        cycle_speed_kmh: float = DEFAULT_CYCLE_SPEED_KMH,
        station_access_time: float = STATION_ACCESS_TIME_MINUTES,
        train_waiting_time: float = TRAIN_WAITING_TIME_MINUTES,
        line_change_time: float = LINE_CHANGE_TIME_MINUTES,
    ):
        """
        Initialize router with multi-layer merged graph.

        Args:
            graph_file: Path to multi-layer merged graph pickle file
            cycle_speed_kmh: Cycling speed in km/h
            station_access_time: Time to enter/exit station in minutes
            train_waiting_time: Average time waiting for train in minutes
            line_change_time: Time to change between tube lines in minutes
        """
        self.cycle_speed_kmh = validate_cycle_speed(cycle_speed_kmh)
        self.station_access_time = station_access_time
        self.train_waiting_time = train_waiting_time
        self._line_change_time = line_change_time
        self.graph = self._load_graph(graph_file)
        self.bike_router = create_google_maps_router()

    @property
    def line_change_time(self) -> float:
        """Get current line change time in minutes."""
        return self._line_change_time

    @line_change_time.setter
    def line_change_time(self, value: float) -> None:
        """Set line change time and update all line change edges in the graph."""
        self._line_change_time = value
        self._update_line_change_edges(value)

    def _update_line_change_edges(self, line_change_time: float) -> None:
        """Update all line change edge weights with new duration."""
        updated_count = 0
        for u, v, data in self.graph.edges(data=True):
            if data.get("edge_type") == "line_change":
                self.graph[u][v]["duration_minutes"] = line_change_time
                updated_count += 1

        if updated_count > 0:
            print(f"Updated {updated_count} line change edges to {line_change_time} minutes")

    def _load_graph(self, graph_file: str) -> nx.Graph:
        """Load multi-layer merged graph from pickle file and apply station access buffers."""
        print(f"Loading multi-layer routing graph from {graph_file}...")

        try:
            with open(graph_file, "rb") as f:
                graph = pickle.load(f)

            # Count unique stations
            unique_stations = set()
            for _node_id, node_data in graph.nodes(data=True):
                station_id = node_data.get("station_id")
                if station_id:
                    unique_stations.add(station_id)

            print(
                f"✅ Loaded multi-layer graph: {graph.number_of_nodes()} nodes "
                f"({len(unique_stations)} unique stations), {graph.number_of_edges()} connections"
            )

            # Apply station access buffers to existing bike edges
            self._apply_station_access_buffers(graph)

            return graph

        except FileNotFoundError:
            print(f"❌ Graph file not found: {graph_file}")
            print("   Run merge_multilayer_graphs.py first to create the multi-layer network")
            sys.exit(1)

    def _calculate_bike_edge_buffer(self, node1: str, node2: str) -> float:
        """
        Calculate station access buffer for bike edges.

        Args:
            node1: Source node ID
            node2: Target node ID

        Returns:
            Buffer time in minutes
        """
        is_start = node1 == "start"
        is_end = node2 == "end"
        is_station1 = node1 not in ["start", "end"]
        is_station2 = node2 not in ["start", "end"]

        if is_start and is_station2:
            # Start → Station: entry + wait for train
            return self.station_access_time + self.train_waiting_time
        elif is_station1 and is_end:
            # Station → End: exit only
            return self.station_access_time
        elif is_station1 and is_station2:
            # Station → Station: exit + entry + wait for train
            return self.station_access_time + self.station_access_time + self.train_waiting_time
        else:
            # Direct start → end or other edges: no buffer
            return 0.0

    def _apply_station_access_buffers(self, graph: nx.Graph):
        """Apply station access buffers to all bike edges in the graph."""
        print("\nApplying station access buffers to bike edges...")

        bike_edges_modified = 0
        total_buffer_added = 0.0

        # Process all bike edges in the graph
        for node1, node2, edge_data in graph.edges(data=True):
            if edge_data.get("transport_mode") == "bike":
                buffer = self._calculate_bike_edge_buffer(node1, node2)

                if buffer > 0:
                    # Store original duration before applying buffer
                    if "original_duration_minutes" not in edge_data:
                        edge_data["original_duration_minutes"] = edge_data["duration_minutes"]

                    # Apply buffer
                    edge_data["duration_minutes"] += buffer
                    edge_data["station_access_buffer_minutes"] = buffer

                    bike_edges_modified += 1
                    total_buffer_added += buffer

        print(f"✅ Applied buffers to {bike_edges_modified} bike edges")
        print(f"   Average buffer: {total_buffer_added / max(bike_edges_modified, 1):.1f} minutes")
        print(
            f"   Station access: {self.station_access_time} min, Train wait: {self.train_waiting_time} min"
        )

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

    def _collect_unique_stations(self) -> dict[str, dict]:
        """
        Collect unique stations from multi-layer nodes.

        Returns:
            Dict mapping station_id to station info including all node variants
        """
        unique_stations = {}

        for node_id, node_data in self.graph.nodes(data=True):
            station_id = node_data.get("station_id")
            if station_id:
                if station_id not in unique_stations:
                    unique_stations[station_id] = {
                        "coords": (node_data["lon"], node_data["lat"]),
                        "name": node_data.get("station_name", ""),
                        "node_ids": [],
                    }
                unique_stations[station_id]["node_ids"].append(node_id)

        return unique_stations

    def _add_virtual_nodes(
        self,
        start_coords: tuple[float, float],
        end_coords: tuple[float, float],
        max_bike_only_minutes: float = 45.0,
    ) -> nx.Graph:
        """
        Add virtual start/end nodes with bike connections to all station line variants.
        Optimized to make API calls only for unique stations, not every line variant.

        Args:
            start_coords: (longitude, latitude) of start point
            end_coords: (longitude, latitude) of end point
            max_bike_only_minutes: Maximum cycling time threshold

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

        # Collect unique stations to avoid redundant API calls
        unique_stations = self._collect_unique_stations()

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
        print(
            f"  📊 Processing {len(unique_stations)} unique stations (not {self.graph.number_of_nodes()} nodes)"
        )

        start_time = time.time()
        edges_added = 0
        stations_filtered = 0

        # Filter unique stations by distance first
        stations_to_query = []
        for station_id, station_info in unique_stations.items():
            distance_km = self._calculate_haversine_distance(start_coords, station_info["coords"])

            if distance_km <= max_straight_line_km:
                stations_to_query.append((station_id, station_info))
            else:
                stations_filtered += 1

        print(
            f"  📊 Querying {len(stations_to_query)} stations (filtered {stations_filtered} distant stations)"
        )

        # Add bike edges from start to filtered stations using parallel requests
        with ThreadPoolExecutor(max_workers=30) as executor:
            # Submit route calculations for unique stations only
            futures = {}
            for station_id, station_info in stations_to_query:
                future = executor.submit(
                    self.bike_router.get_route, start_coords, station_info["coords"]
                )
                futures[future] = (station_id, station_info)

            # Process results and add edges to ALL line variants
            for future in as_completed(futures):
                station_id, station_info = futures[future]
                try:
                    result = future.result()
                    if result.success and result.duration_minutes > 0:
                        # Add edge to each line variant at this station
                        for node_id in station_info["node_ids"]:
                            # Calculate buffer for start → station edge
                            buffer = self._calculate_bike_edge_buffer("start", node_id)
                            total_duration = result.duration_minutes + buffer

                            augmented_graph.add_edge(
                                "start",
                                node_id,
                                duration_minutes=total_duration,
                                original_duration_minutes=result.duration_minutes,
                                station_access_buffer_minutes=buffer,
                                transport_mode="bike",
                                distance_km=result.distance_km,
                                line=None,
                            )
                        edges_added += len(station_info["node_ids"])
                except Exception as e:
                    print(f"  ⚠️  Error calculating route to station {station_id}: {e}")

        print(f"✅ Added {edges_added} bike routes from start ({time.time() - start_time:.1f}s)")

        # Repeat for end location
        print("\nCalculating bike routes to end location...")
        print(
            f"  🎯 Filtering stations within {max_straight_line_km:.1f} km straight-line distance"
        )

        start_time = time.time()
        edges_added = 0
        stations_filtered = 0

        # Filter unique stations by distance
        stations_to_query = []
        for station_id, station_info in unique_stations.items():
            distance_km = self._calculate_haversine_distance(station_info["coords"], end_coords)

            if distance_km <= max_straight_line_km:
                stations_to_query.append((station_id, station_info))
            else:
                stations_filtered += 1

        print(
            f"  📊 Querying {len(stations_to_query)} stations (filtered {stations_filtered} distant stations)"
        )

        # Add bike edges from filtered stations to end using parallel requests
        with ThreadPoolExecutor(max_workers=30) as executor:
            # Submit route calculations for unique stations only
            futures = {}
            for station_id, station_info in stations_to_query:
                future = executor.submit(
                    self.bike_router.get_route, station_info["coords"], end_coords
                )
                futures[future] = (station_id, station_info)

            # Process results and add edges from ALL line variants
            for future in as_completed(futures):
                station_id, station_info = futures[future]
                try:
                    result = future.result()
                    if result.success and result.duration_minutes > 0:
                        # Add edge from each line variant at this station
                        for node_id in station_info["node_ids"]:
                            # Calculate buffer for station → end edge
                            buffer = self._calculate_bike_edge_buffer(node_id, "end")
                            total_duration = result.duration_minutes + buffer

                            augmented_graph.add_edge(
                                node_id,
                                "end",
                                duration_minutes=total_duration,
                                original_duration_minutes=result.duration_minutes,
                                station_access_buffer_minutes=buffer,
                                transport_mode="bike",
                                distance_km=result.distance_km,
                                line=None,
                            )
                        edges_added += len(station_info["node_ids"])
                except Exception as e:
                    print(f"  ⚠️  Error calculating route from station {station_id}: {e}")

        print(f"✅ Added {edges_added} bike routes to end ({time.time() - start_time:.1f}s)")

        return augmented_graph

    def _extract_station_and_line(self, node_id: str) -> tuple[str, str]:
        """
        Extract station ID and line from a multi-layer node ID.

        Args:
            node_id: Node ID like "940GZZLUBST_jubilee" or "start"

        Returns:
            (station_id, line) tuple
        """
        if node_id in ["start", "end"]:
            return node_id, None

        parts = node_id.split("_", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return node_id, None

    def _process_multilayer_path(self, path: list[str], augmented_graph: nx.Graph) -> list[dict]:
        """
        Process multi-layer path to create formatted segments with line change detection.

        Args:
            path: List of node IDs in the path
            augmented_graph: Graph with path edges

        Returns:
            List of processed segments with line change information
        """
        segments = []

        for i in range(len(path) - 1):
            current_node = path[i]
            next_node = path[i + 1]

            edge_data = augmented_graph[current_node][next_node]

            # Extract station and line info
            current_station, current_line = self._extract_station_and_line(current_node)
            next_station, next_line = self._extract_station_and_line(next_node)

            # Get node data for names
            current_data = augmented_graph.nodes[current_node]
            next_data = augmented_graph.nodes[next_node]

            segment = {
                "from_node": current_node,
                "to_node": next_node,
                "from_station": current_station,
                "to_station": next_station,
                "from_line": current_line,
                "to_line": next_line,
                "from_name": current_data.get(
                    "station_name", current_data.get("name", current_node)
                ),
                "to_name": next_data.get("station_name", next_data.get("name", next_node)),
                "duration_minutes": edge_data["duration_minutes"],
                "transport_mode": edge_data["transport_mode"],
                "edge_type": edge_data.get("edge_type", "travel"),
            }

            # Add mode-specific data
            if edge_data["transport_mode"] == "bike":
                segment["distance_km"] = edge_data.get("distance_km")
                segment["original_duration_minutes"] = edge_data.get("original_duration_minutes")
                segment["station_access_buffer_minutes"] = edge_data.get(
                    "station_access_buffer_minutes", 0.0
                )
            elif edge_data["transport_mode"] == "tube":
                segment["tube_line"] = edge_data.get("line", current_line)

            segments.append(segment)

        return segments

    def find_optimal_route(
        self,
        start_coords: tuple[float, float],
        end_coords: tuple[float, float],
        max_bike_only_minutes: float = 45.0,
    ) -> dict | None:
        """
        Find optimal multi-modal route between two coordinates.
        Always compares direct bike vs multi-modal and returns the shortest route.

        Args:
            start_coords: (longitude, latitude) of start point
            end_coords: (longitude, latitude) of end point
            max_bike_only_minutes: Distance threshold for bike connections to stations

        Returns:
            Route information or None if no route found
        """
        # Calculate direct bike route for comparison
        print("\nCalculating direct bike route...")
        direct_bike = self.bike_router.get_route(start_coords, end_coords)
        direct_bike_duration = float("inf")  # Default to infinity if bike route fails

        if direct_bike.success:
            direct_bike_duration = direct_bike.duration_minutes
            print(
                f"Direct bike: {direct_bike.duration_minutes:.1f} minutes, {direct_bike.distance_km:.1f} km"
            )

        # Create augmented graph with virtual nodes
        print("\nBuilding augmented graph with bike connections...")
        augmented_graph = self._add_virtual_nodes(start_coords, end_coords, max_bike_only_minutes)

        # Run Dijkstra's algorithm to find multi-modal route
        print("\nRunning Dijkstra's algorithm on multi-layer graph...")
        multi_modal_route = None
        multi_modal_duration = float("inf")

        try:
            # Find shortest path using duration as weight
            path = nx.shortest_path(
                augmented_graph, source="start", target="end", weight="duration_minutes"
            )

            # Process path to extract segments with line change info
            segments = self._process_multilayer_path(path, augmented_graph)

            # Calculate total duration (no need for buffer adjustment - line changes are in the graph!)
            multi_modal_duration = sum(seg["duration_minutes"] for seg in segments)

            print(
                f"✅ Found multi-modal route: {len(path)} nodes, {multi_modal_duration:.1f} minutes total"
            )

            multi_modal_route = {
                "path": path,
                "segments": segments,
                "total_duration": multi_modal_duration,
                "is_direct_bike": False,
            }

        except nx.NetworkXNoPath:
            print("❌ No multi-modal route found between start and end locations")
        except Exception as e:
            print(f"❌ Error finding multi-modal route: {e}")
            import traceback

            traceback.print_exc()

        # Compare routes and return the optimal one
        print("\nComparing routes:")
        print(f"  Direct bike: {direct_bike_duration:.1f} minutes")
        print(f"  Multi-modal: {multi_modal_duration:.1f} minutes")

        # Return the shortest route
        if direct_bike.success and direct_bike_duration <= multi_modal_duration:
            print(f"✅ Direct bike route is optimal ({direct_bike_duration:.1f} min)")

            return {
                "path": ["start", "end"],
                "segments": [
                    {
                        "from_node": "start",
                        "to_node": "end",
                        "from_station": "start",
                        "to_station": "end",
                        "from_name": "Start Location",
                        "to_name": "End Location",
                        "duration_minutes": direct_bike.duration_minutes,
                        "original_duration_minutes": direct_bike.duration_minutes,
                        "station_access_buffer_minutes": 0.0,
                        "transport_mode": "bike",
                        "distance_km": direct_bike.distance_km,
                        "edge_type": "travel",
                    }
                ],
                "total_duration": direct_bike.duration_minutes,
                "is_direct_bike": True,
            }
        elif multi_modal_route:
            print(f"✅ Multi-modal route is optimal ({multi_modal_duration:.1f} min)")
            return multi_modal_route
        else:
            print("❌ No valid route found")
            return None

    def format_route(
        self,
        route_info: dict,
        output_format: str = "detailed",
        start_name: str = "Your location",
        end_name: str = "Your destination",
    ) -> str:
        """
        Format route information for display with multi-layer awareness.

        Args:
            route_info: Route information from find_optimal_route
            output_format: Output format (simple/detailed/json)
            start_name: Name for start location
            end_name: Name for end location

        Returns:
            Formatted route string
        """
        if not route_info:
            return "No route found"

        segments = route_info["segments"]
        total_duration = route_info["total_duration"]

        # Build formatted output
        lines = []
        lines.append(f"\n{'=' * 60}")
        lines.append(f"🗺️  ROUTE: {start_name} → {end_name}")
        lines.append(f"⏱️  Total time: {total_duration:.0f} minutes")

        # Count transport modes
        bike_count = sum(1 for s in segments if s["transport_mode"] == "bike")
        tube_count = sum(
            1 for s in segments if s["transport_mode"] == "tube" and s["edge_type"] != "line_change"
        )
        line_change_count = sum(1 for s in segments if s["edge_type"] == "line_change")

        mode_summary = []
        if bike_count > 0:
            mode_summary.append(f"{bike_count} bike")
        if tube_count > 0:
            mode_summary.append(f"{tube_count} tube")
        if line_change_count > 0:
            mode_summary.append(
                f"{line_change_count} line change{'s' if line_change_count > 1 else ''}"
            )

        lines.append(f"🚀 Segments: {' + '.join(mode_summary)}")
        lines.append(f"{'=' * 60}\n")

        # Format each segment
        for i, segment in enumerate(segments):
            mode = segment["transport_mode"]
            duration = segment["duration_minutes"]

            if segment["edge_type"] == "line_change":
                # Line change segment
                lines.append(f"{i + 1}. 🔄 LINE CHANGE at {segment['from_name']}")
                lines.append(f"   {segment['from_line'].title()} → {segment['to_line'].title()}")
                lines.append(f"   Duration: {duration:.0f} minutes")
            else:
                # Regular travel segment
                emoji = get_transport_emoji(mode)

                # Format station names with lines for tube segments
                if mode == "tube":
                    from_display = f"{segment['from_name']} ({segment['from_line'].title()})"
                    to_display = f"{segment['to_name']} ({segment['to_line'].title()})"
                else:
                    from_display = segment["from_name"]
                    to_display = segment["to_name"]

                lines.append(f"{i + 1}. {emoji} {mode.upper()}: {from_display} → {to_display}")
                lines.append(f"   Duration: {duration:.0f} minutes")

                if mode == "bike":
                    if segment.get("distance_km"):
                        lines.append(f"   Distance: {segment['distance_km']:.1f} km")

                    # Show buffer breakdown for bike segments
                    original_time = segment.get("original_duration_minutes", duration)
                    buffer_time = segment.get("station_access_buffer_minutes", 0.0)
                    if buffer_time > 0:
                        lines.append(
                            f"   Bike time: {original_time:.0f} min + Station access: {buffer_time:.0f} min"
                        )

                elif mode == "tube" and segment.get("tube_line"):
                    lines.append(f"   Line: {segment['tube_line'].title()}")

            lines.append("")

        lines.append(f"{'=' * 60}")
        lines.append(f"📍 Total journey time: {total_duration:.0f} minutes")
        lines.append(f"{'=' * 60}\n")

        return "\n".join(lines)


def main():
    """Command-line interface for multi-layer route planning."""
    parser = argparse.ArgumentParser(
        description="Find optimal bike+tube routes in London using multi-layer graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find route using coordinates
  python route_planner_multilayer.py -0.1278 51.5074 -0.0772 51.5031

  # With custom cycling speed
  python route_planner_multilayer.py -0.1278 51.5074 -0.0772 51.5031 --speed 12

  # Using different graph file
  python route_planner_multilayer.py -0.1278 51.5074 -0.0772 51.5031 --graph my_graph.pickle
        """,
    )

    parser.add_argument(
        "start_lon", type=float, help="Starting longitude (e.g., -0.1278 for Central London)"
    )
    parser.add_argument(
        "start_lat", type=float, help="Starting latitude (e.g., 51.5074 for Central London)"
    )
    parser.add_argument(
        "end_lon", type=float, help="Ending longitude (e.g., -0.0772 for East London)"
    )
    parser.add_argument(
        "end_lat", type=float, help="Ending latitude (e.g., 51.5031 for East London)"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=DEFAULT_CYCLE_SPEED_KMH,
        help=f"Cycling speed in km/h (default: {DEFAULT_CYCLE_SPEED_KMH})",
    )
    parser.add_argument(
        "--graph",
        default="merged_multilayer_graph.pickle",
        help="Path to multi-layer graph file (default: merged_multilayer_graph.pickle)",
    )
    parser.add_argument(
        "--format",
        choices=["simple", "detailed", "json"],
        default="detailed",
        help="Output format (default: detailed)",
    )
    parser.add_argument(
        "--max-bike",
        type=float,
        default=45.0,
        help="Distance threshold for bike connections to stations (default: 45)",
    )

    args = parser.parse_args()

    # Create router
    router = MultiLayerBikeTransitRouter(graph_file=args.graph, cycle_speed_kmh=args.speed)

    # Find route
    start_coords = (args.start_lon, args.start_lat)
    end_coords = (args.end_lon, args.end_lat)

    print("\n🔍 Finding optimal route...")
    print(f"   From: {start_coords}")
    print(f"   To: {end_coords}")

    route = router.find_optimal_route(start_coords, end_coords, max_bike_only_minutes=args.max_bike)

    if route:
        # Format and display route
        formatted = router.format_route(route, output_format=args.format)
        print(formatted)
    else:
        print("\n❌ No route found between the specified locations")


if __name__ == "__main__":
    main()
