# ABOUTME: Builds a NetworkX graph of the London Underground network with stations as nodes and travel times as edges
# ABOUTME: Optimized for shortest path algorithms like Dijkstra's, saves in multiple formats for flexibility

import argparse
import json
import pickle
import time
from pathlib import Path

import networkx as nx

from tfl_utils import TfLStationUtils


class TfLGraphBuilder:
    """Builds a graph representation of the London Underground network"""

    def __init__(
        self, stations_file: str = "../data/tfl_stations.json", continue_from_cache: bool = False
    ):
        """Initialize with station data"""
        self.utils = TfLStationUtils(stations_file)
        self.graph = nx.Graph()
        self.travel_time_cache = {}
        self.failed_connections = []
        self.progress_file = "../data/tfl_graph_progress.json"

        if continue_from_cache:
            self._load_progress()

    def _save_progress(self):
        """Save current progress to resume later"""
        # Convert cache keys to JSON-serializable format
        cache_json = {f"{k[0]}|{k[1]}": v for k, v in self.travel_time_cache.items()}

        progress_data = {
            "travel_time_cache": cache_json,
            "failed_connections": self.failed_connections,
            "processed_edges": self.graph.number_of_edges(),
            "timestamp": time.time(),
        }

        with open(self.progress_file, "w") as f:
            json.dump(progress_data, f, indent=2)

    def _load_progress(self):
        """Load previous progress if available"""
        if Path(self.progress_file).exists():
            print("Loading previous progress...")
            with open(self.progress_file) as f:
                progress_data = json.load(f)

            # Convert cache back to tuple keys
            cache_json = progress_data.get("travel_time_cache", {})
            self.travel_time_cache = {tuple(k.split("|")): v for k, v in cache_json.items()}

            self.failed_connections = progress_data.get("failed_connections", [])

            print(f"Loaded {len(self.travel_time_cache)} cached travel times")
            print(f"Loaded {len(self.failed_connections)} previous failures")
        else:
            print("No previous progress found, starting fresh")

    def _get_cached_travel_time(self, station1_id: str, station2_id: str) -> int | None:
        """Get travel time with caching to avoid repeated API calls"""
        # Create a sorted key to handle bidirectional edges
        cache_key = tuple(sorted([station1_id, station2_id]))

        if cache_key in self.travel_time_cache:
            return self.travel_time_cache[cache_key]

        # Get station names for the API call
        station1_data = self.utils.get_station_info(station1_id)
        station2_data = self.utils.get_station_info(station2_id)

        if not station1_data or not station2_data:
            print(f"Warning: Could not find station data for {station1_id} or {station2_id}")
            return None

        # Make API call using station names with retry logic
        max_retries = 2
        for attempt in range(max_retries + 1):
            result = self.utils.get_journey_time(
                station1_data["name"], station2_data["name"], by_name=True
            )

            if result.success and result.duration_minutes >= 0:
                travel_time = result.duration_minutes
                self.travel_time_cache[cache_key] = travel_time
                print(f"  {station1_data['name']} ↔ {station2_data['name']}: {travel_time} min")
                return travel_time
            elif attempt < max_retries:
                print(
                    f"  Retry {attempt + 1}/{max_retries}: {station1_data['name']} ↔ {station2_data['name']}"
                )
                time.sleep(1.0)  # Wait longer before retry
            else:
                print(
                    f"  Failed to get travel time: {station1_data['name']} ↔ {station2_data['name']}"
                )
                self.failed_connections.append((station1_id, station2_id, result.error_message))
                return None

    def build_graph(self) -> nx.Graph:
        """Build the complete TfL network graph"""
        print("Building TfL network graph...")
        stations_data = self.utils.stations_data["stations"]

        # Add all stations as nodes
        print(f"Adding {len(stations_data)} stations as nodes...")
        for station_id, station in stations_data.items():
            self.graph.add_node(
                station_id,
                name=station["name"],
                lat=station["lat"],
                lon=station["lon"],
                lines=station["lines"],
                zone=station.get("zone"),
                connection_count=station.get("connection_count", 0),
            )

        # Add edges based on station connections with travel times
        print("Adding edges with travel times...")
        total_connections = 0
        processed_pairs = set()

        for station_id, station in stations_data.items():
            connections = station.get("connections", [])

            for connection in connections:
                to_station_id = connection["to_station"]

                # Create a sorted pair to avoid duplicate processing
                connection_pair = tuple(sorted([station_id, to_station_id]))
                if connection_pair in processed_pairs:
                    continue

                processed_pairs.add(connection_pair)

                # Get travel time between stations
                travel_time = self._get_cached_travel_time(station_id, to_station_id)

                if travel_time is not None:
                    # Add edge with travel time as weight
                    self.graph.add_edge(
                        station_id,
                        to_station_id,
                        weight=travel_time,
                        line=connection["line"],
                        direction=connection.get("direction", "unknown"),
                    )
                    total_connections += 1

                # Rate limiting for API calls (increased for stability)
                time.sleep(0.2)

                # Save progress periodically (every 50 connections)
                if total_connections % 50 == 0:
                    self._save_progress()
                    print(f"  Progress saved at {total_connections} edges")

        print("Graph construction complete!")
        print(f"Nodes (stations): {self.graph.number_of_nodes()}")
        print(f"Edges (connections): {self.graph.number_of_edges()}")
        print(f"Failed connections: {len(self.failed_connections)}")

        # Save final progress
        self._save_progress()
        print("Final progress saved")

        return self.graph

    def save_graph(self, base_filename: str = "tfl_graph"):
        """Save graph in multiple formats"""
        print("Saving graph to multiple formats...")

        # Save as NetworkX pickle (preserves all graph properties)
        networkx_file = f"{base_filename}.pickle"
        with open(networkx_file, "wb") as f:
            pickle.dump(self.graph, f)
        print(f"✓ NetworkX graph saved to: {networkx_file}")

        # Save as simple adjacency dictionary (JSON format)
        # Convert travel_time_cache to JSON-serializable format (tuple keys to string)
        travel_time_cache_json = {
            f"{key[0]}|{key[1]}": value for key, value in self.travel_time_cache.items()
        }

        adjacency_dict = {
            "metadata": {
                "nodes": self.graph.number_of_nodes(),
                "edges": self.graph.number_of_edges(),
                "failed_connections": len(self.failed_connections),
                "description": "TfL Underground network graph - adjacency list format",
            },
            "nodes": dict(self.graph.nodes(data=True)),
            "edges": dict(self.graph.adjacency()),
            "travel_time_cache": travel_time_cache_json,
            "failed_connections": self.failed_connections,
        }

        json_file = f"{base_filename}.json"
        with open(json_file, "w") as f:
            json.dump(adjacency_dict, f, indent=2, ensure_ascii=False)
        print(f"✓ Adjacency dict saved to: {json_file}")

        # Save as searchable station name lookup (JSON format)
        searchable_dict = {
            "metadata": {
                "nodes": self.graph.number_of_nodes(),
                "edges": self.graph.number_of_edges(),
                "description": "TfL Underground network - searchable by station name",
                "format": "station_name -> [[neighbor_name, travel_time_minutes], ...]",
            }
        }

        # Build station name -> neighbors mapping
        for node_id, node_data in self.graph.nodes(data=True):
            station_name = node_data["name"]
            neighbors = []

            for neighbor_id in self.graph.neighbors(node_id):
                neighbor_data = self.graph.nodes[neighbor_id]
                neighbor_name = neighbor_data["name"]
                travel_time = self.graph[node_id][neighbor_id].get("weight", 0)
                neighbors.append([neighbor_name, travel_time])

            # Sort neighbors by travel time
            neighbors.sort(key=lambda x: x[1])
            searchable_dict[station_name] = neighbors

        searchable_file = f"{base_filename}_searchable.json"
        with open(searchable_file, "w") as f:
            json.dump(searchable_dict, f, indent=2, ensure_ascii=False)
        print(f"✓ Searchable station lookup saved to: {searchable_file}")

    def validate_graph(self) -> bool:
        """Validate the constructed graph"""
        print("\nValidating graph structure...")

        # Check if graph is connected
        if not nx.is_connected(self.graph):
            print("❌ Warning: Graph is not fully connected")
            components = list(nx.connected_components(self.graph))
            print(f"   Number of connected components: {len(components)}")
            for i, component in enumerate(components[:3]):  # Show first 3 components
                print(f"   Component {i + 1}: {len(component)} nodes")
        else:
            print("✓ Graph is fully connected")

        # Check for isolated nodes
        isolated_nodes = list(nx.isolates(self.graph))
        if isolated_nodes:
            print(f"❌ Warning: {len(isolated_nodes)} isolated nodes found")
            for node_id in isolated_nodes[:5]:  # Show first 5
                node_data = self.graph.nodes[node_id]
                print(f"   Isolated: {node_data['name']}")
        else:
            print("✓ No isolated nodes")

        # Check edge weights
        zero_weight_edges = [
            (u, v) for u, v, d in self.graph.edges(data=True) if d.get("weight", 0) <= 0
        ]
        if zero_weight_edges:
            print(f"❌ Warning: {len(zero_weight_edges)} edges with zero/negative weights")
        else:
            print("✓ All edges have positive weights")

        # Sample shortest path calculation
        print("\nTesting shortest path algorithms...")
        try:
            # Test with Baker Street and Kings Cross
            baker_id = None
            kings_id = None

            for node_id, data in self.graph.nodes(data=True):
                if "Baker Street" in data["name"]:
                    baker_id = node_id
                elif "King" in data["name"] and "Cross" in data["name"]:
                    kings_id = node_id

            if baker_id and kings_id:
                path = nx.shortest_path(self.graph, baker_id, kings_id, weight="weight")
                path_length = nx.shortest_path_length(
                    self.graph, baker_id, kings_id, weight="weight"
                )
                print(f"✓ Shortest path Baker Street → Kings Cross: {path_length:.0f} minutes")
                print(f"   Path length: {len(path)} stations")
            else:
                print("❌ Could not find Baker Street or Kings Cross for testing")

        except nx.NetworkXNoPath:
            print("❌ No path found between test stations")
        except Exception as e:
            print(f"❌ Error testing shortest path: {e}")

        return len(isolated_nodes) == 0 and len(zero_weight_edges) == 0

    def retry_failed_connections(self):
        """Retry only the previously failed connections"""
        if not self.failed_connections:
            print("No failed connections to retry")
            return

        print(f"Retrying {len(self.failed_connections)} failed connections...")

        # Always rebuild from the complete cached progress to ensure we have all successful connections
        self._rebuild_graph_from_cache()

        # Copy the failed connections list and clear it
        retry_list = self.failed_connections.copy()
        self.failed_connections = []

        successful_retries = 0

        for station1_id, station2_id, _error in retry_list:
            # Check if already cached
            cache_key = tuple(sorted([station1_id, station2_id]))
            if cache_key in self.travel_time_cache:
                print(f"  Skipping cached: {station1_id} ↔ {station2_id}")
                continue

            print(f"  Retrying: {station1_id} ↔ {station2_id}")
            travel_time = self._get_cached_travel_time(station1_id, station2_id)

            if travel_time is not None:
                # Add to graph if successful
                self.graph.add_edge(station1_id, station2_id, weight=travel_time)
                successful_retries += 1

        print(
            f"Retry complete: {successful_retries} successful, {len(self.failed_connections)} still failed"
        )

        # Save updated progress with new successful connections
        self._save_progress()

        # Print summary statistics after retry
        print("\nAfter retry - Graph summary:")
        print(f"  Nodes: {self.graph.number_of_nodes()}")
        print(f"  Edges: {self.graph.number_of_edges()}")
        print(f"  Failed connections remaining: {len(self.failed_connections)}")

    def _rebuild_graph_from_cache(self):
        """Rebuild the graph structure from cached travel times"""
        print("Rebuilding graph from cache...")
        stations_data = self.utils.stations_data["stations"]

        # Add all stations as nodes
        for station_id, station in stations_data.items():
            self.graph.add_node(
                station_id,
                name=station["name"],
                lat=station["lat"],
                lon=station["lon"],
                lines=station["lines"],
                zone=station.get("zone"),
                connection_count=station.get("connection_count", 0),
            )

        # Add edges from cache
        for cache_key, travel_time in self.travel_time_cache.items():
            station1_id, station2_id = cache_key
            if not self.graph.has_edge(station1_id, station2_id):
                self.graph.add_edge(station1_id, station2_id, weight=travel_time)

        print(
            f"Rebuilt graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges"
        )

    def print_graph_stats(self):
        """Print detailed graph statistics"""
        print("\n" + "=" * 50)
        print("TFL GRAPH STATISTICS")
        print("=" * 50)

        print(f"Nodes (stations): {self.graph.number_of_nodes()}")
        print(f"Edges (connections): {self.graph.number_of_edges()}")
        print(f"Graph density: {nx.density(self.graph):.4f}")

        # Degree statistics
        degrees = [self.graph.degree(node) for node in self.graph.nodes()]
        print("\nDegree statistics:")
        print(f"  Average degree: {sum(degrees) / len(degrees):.2f}")
        print(f"  Maximum degree: {max(degrees)}")
        print(f"  Minimum degree: {min(degrees)}")

        # Most connected stations
        most_connected = sorted(
            [
                (node, self.graph.degree(node), data["name"])
                for node, data in self.graph.nodes(data=True)
            ],
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        print("\nMost connected stations:")
        for _node_id, degree, name in most_connected:
            print(f"  {name}: {degree} connections")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Build TfL network graph")
    parser.add_argument(
        "--continue",
        dest="continue_build",
        action="store_true",
        help="Continue from previous progress (resume failed connections)",
    )
    parser.add_argument(
        "--retry-failed", action="store_true", help="Retry only the previously failed connections"
    )
    args = parser.parse_args()

    print("TfL Network Graph Builder")
    print("=" * 40)

    # Check if station data exists
    if not Path("tfl_stations.json").exists():
        print("Error: tfl_stations.json not found. Run fetch_tfl_stations.py first.")
        return False

    # Build the graph
    if args.retry_failed:
        print("Retrying previously failed connections...")
        builder = TfLGraphBuilder(continue_from_cache=True)
        builder.retry_failed_connections()
    else:
        print("Building graph..." + (" (continuing from cache)" if args.continue_build else ""))
        builder = TfLGraphBuilder(continue_from_cache=args.continue_build)
        builder.build_graph()

    # Validate the graph
    is_valid = builder.validate_graph()

    # Print statistics
    builder.print_graph_stats()

    # Save the graph
    builder.save_graph("../data/tfl_graph")

    print(
        f"\nGraph construction {'completed successfully' if is_valid else 'completed with warnings'}"
    )
    return is_valid


if __name__ == "__main__":
    main()
