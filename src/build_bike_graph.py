#!/usr/bin/env python3
"""
ABOUTME: Build NetworkX graph of bike routes between all TfL stations with resume functionality
ABOUTME: Creates bike routing network with travel times as edge weights, supports caching and progress tracking
"""

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import networkx as nx

from bike_routing import create_default_router
from tfl_utils import TfLStationUtils


def load_progress(progress_file: str) -> tuple[dict, set, int]:
    """
    Load progress from previous run.

    Returns:
        (bike_time_cache, processed_pairs, total_processed)
    """
    try:
        with open(progress_file) as f:
            data = json.load(f)

        bike_time_cache = {}
        # Convert pipe-delimited keys back to tuples
        for key, value in data.get("bike_time_cache", {}).items():
            station1, station2 = key.split("|")
            bike_time_cache[(station1, station2)] = value

        processed_pairs = set()
        for pair_str in data.get("processed_pairs", []):
            station1, station2 = pair_str.split("|")
            processed_pairs.add((station1, station2))

        total_processed = data.get("total_processed", 0)

        print(
            f"✅ Loaded progress: {total_processed} pairs processed, {len(bike_time_cache)} cached results"
        )
        return bike_time_cache, processed_pairs, total_processed

    except FileNotFoundError:
        print("🔄 No previous progress found, starting fresh")
        return {}, set(), 0
    except Exception as e:
        print(f"⚠️  Error loading progress: {e}")
        return {}, set(), 0


def save_progress(
    progress_file: str, bike_time_cache: dict, processed_pairs: set, total_processed: int
):
    """Save current progress to JSON file."""
    # Convert tuple keys to pipe-delimited strings for JSON serialization
    cache_serializable = {}
    for (station1, station2), value in bike_time_cache.items():
        cache_serializable[f"{station1}|{station2}"] = value

    pairs_serializable = [f"{station1}|{station2}" for station1, station2 in processed_pairs]

    progress_data = {
        "bike_time_cache": cache_serializable,
        "processed_pairs": pairs_serializable,
        "total_processed": total_processed,
        "timestamp": time.time(),
    }

    with open(progress_file, "w") as f:
        json.dump(progress_data, f, indent=2)


def get_bike_time_between_stations(
    tfl_utils: TfLStationUtils, station1_data: dict, station2_data: dict
) -> float | None:
    """
    Get bike routing time between two stations.
    Automatically tries reverse direction if initial route fails.

    Returns:
        Duration in minutes, or None if routing failed in both directions
    """
    start_coords = (station1_data["lon"], station1_data["lat"])
    end_coords = (station2_data["lon"], station2_data["lat"])

    try:
        # Try original direction
        result = tfl_utils.get_bike_route(start_coords, end_coords)

        if result.success:
            return result.duration_minutes

        # If failed, try reverse direction
        print("    ↔️  Trying reverse direction...")
        reverse_result = tfl_utils.get_bike_route(end_coords, start_coords)

        if reverse_result.success:
            print("    ✅ Reverse routing succeeded")
            return reverse_result.duration_minutes
        else:
            print(f"    ❌ Both directions failed: {result.error_message}")
            return None

    except Exception as e:
        print(f"    ❌ Exception during bike routing: {e}")
        return None


def build_bike_graph(
    continue_build: bool = False,
    retry_failed: bool = False,
    progress_file: str = "bike_graph_progress.json",
    max_pairs: int | None = None,
    output_name: str = "bike_graph",
) -> nx.Graph:
    """
    Build NetworkX graph of bike routes between TfL stations.

    Args:
        continue_build: Resume from previous progress
        retry_failed: Retry previously failed connections
        progress_file: File to save/load progress
        max_pairs: Maximum number of pairs to process (for testing)

    Returns:
        NetworkX graph with bike routing edges
    """
    print("🚴 Building bike routing graph between TfL stations...")

    # Initialize components
    tfl_utils = TfLStationUtils()
    bike_router = create_default_router()

    print(f"📊 Using bike router: {bike_router.provider_name}")

    # Load station data
    stations = tfl_utils.stations_data["stations"]
    station_list = list(stations.items())
    print(f"📍 Found {len(station_list)} stations")

    # Load previous progress if continuing
    bike_time_cache = {}
    processed_pairs = set()
    total_processed = 0

    if continue_build or retry_failed:
        bike_time_cache, processed_pairs, total_processed = load_progress(progress_file)

    # Create graph or load existing when retrying failed
    if retry_failed and Path(f"{output_name}.pickle").exists():
        # Load existing graph to preserve successful edges
        with open(f"{output_name}.pickle", "rb") as f:
            G = pickle.load(f)
        print(f"✅ Loaded existing graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        # Count failed routes to retry
        failed_count = sum(1 for v in bike_time_cache.values() if v is None)
        print(f"🔄 Found {failed_count} failed routes to retry")
    else:
        # Create new graph
        G = nx.Graph()

        # Add all stations as nodes
        for station_id, station_data in stations.items():
            G.add_node(station_id, **station_data)

        print(f"📊 Added {len(G.nodes)} station nodes to graph")

    # Calculate total pairs needed
    total_pairs = (len(station_list) * (len(station_list) - 1)) // 2
    print(f"🔄 Total station pairs to process: {total_pairs}")

    if max_pairs:
        print(f"🔄 Limited to {max_pairs} pairs for testing")

    # Build edges between all station pairs
    failed_connections = []
    successful_connections = 0
    pairs_processed_this_run = 0

    try:
        for i, (station1_id, station1_data) in enumerate(station_list):
            for _j, (station2_id, station2_data) in enumerate(station_list[i + 1 :], i + 1):
                # Check if we've hit the max pairs limit
                if max_pairs and pairs_processed_this_run >= max_pairs:
                    print(f"🛑 Reached max pairs limit ({max_pairs})")
                    break

                pair_key = (station1_id, station2_id)

                # Skip logic based on mode
                if retry_failed:
                    # When retrying failed, skip successful pairs
                    if pair_key in bike_time_cache and bike_time_cache[pair_key] is not None:
                        continue
                elif pair_key in processed_pairs:
                    # Normal mode: skip already processed pairs
                    continue

                # Check cache first
                duration_minutes = bike_time_cache.get(pair_key)

                # Show different output for retry mode
                if retry_failed:
                    print(
                        f"\n🔄 RETRY [{pairs_processed_this_run + 1}] {station1_data['name']} ↔ {station2_data['name']}"
                    )
                else:
                    print(
                        f"\n[{total_processed + 1:4d}/{total_pairs}] {station1_data['name']} ↔ {station2_data['name']}"
                    )

                if duration_minutes is None:
                    # Make API call with retries
                    for attempt in range(2):
                        duration_minutes = get_bike_time_between_stations(
                            tfl_utils, station1_data, station2_data
                        )

                        if duration_minutes is not None:
                            break
                        elif attempt == 0:
                            print("    🔄 Retrying...")
                            time.sleep(1)

                    # Cache the result (even if None for failed attempts)
                    bike_time_cache[pair_key] = duration_minutes

                # Add edge if successful
                if duration_minutes is not None and duration_minutes >= 0:
                    # Add bidirectional edge
                    G.add_edge(
                        station1_id,
                        station2_id,
                        duration_minutes=duration_minutes,
                        transport_mode="bike",
                        distance_km=None,
                    )  # Could be added later if needed

                    successful_connections += 1
                    print(f"    ✅ {duration_minutes:.1f} minutes")
                else:
                    failed_connections.append((station1_data["name"], station2_data["name"]))
                    print("    ❌ Failed")

                # Mark as processed
                processed_pairs.add(pair_key)
                total_processed += 1
                pairs_processed_this_run += 1

                # Save progress every 50 pairs
                if pairs_processed_this_run % 50 == 0:
                    save_progress(progress_file, bike_time_cache, processed_pairs, total_processed)
                    print(f"💾 Progress saved ({pairs_processed_this_run} pairs this run)")

                # Rate limiting
                time.sleep(0.1)

            # Break outer loop if max pairs reached
            if max_pairs and pairs_processed_this_run >= max_pairs:
                break

    except KeyboardInterrupt:
        print("\n⏸️  Build interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

    finally:
        # Save final progress
        save_progress(progress_file, bike_time_cache, processed_pairs, total_processed)
        print("💾 Final progress saved")

    # Summary
    if retry_failed:
        print("\n=== RETRY FAILED ROUTES SUMMARY ===")
        print(f"📊 Total edges in graph: {G.number_of_edges()}")
        print(f"✅ Newly successful connections: {successful_connections}")
        print(f"❌ Still failed connections: {len(failed_connections)}")
        print(f"🔄 Routes retried: {pairs_processed_this_run}")
    else:
        print("\n=== BIKE GRAPH BUILD SUMMARY ===")
        print(f"📊 Total edges created: {G.number_of_edges()}")
        print(f"✅ Successful connections: {successful_connections}")
        print(f"❌ Failed connections: {len(failed_connections)}")
        print(f"🔄 Pairs processed this run: {pairs_processed_this_run}")
        print(f"📍 Total pairs processed: {total_processed}/{total_pairs}")

    if failed_connections:
        print("\n❌ Failed connections:")
        for station1, station2 in failed_connections[:10]:  # Show first 10
            print(f"   {station1} ↔ {station2}")
        if len(failed_connections) > 10:
            print(f"   ... and {len(failed_connections) - 10} more")

    return G


def save_graph_formats(graph: nx.Graph, base_name: str = "bike_graph"):
    """Save graph in multiple formats."""
    print("\n💾 Saving graph in multiple formats...")

    # 1. NetworkX pickle (fastest loading)
    pickle_file = f"{base_name}.pickle"
    with open(pickle_file, "wb") as f:
        pickle.dump(graph, f)
    print(f"✅ Saved NetworkX pickle: {pickle_file}")

    # 2. JSON adjacency format
    json_file = f"{base_name}.json"
    graph_data = nx.adjacency_data(graph)
    with open(json_file, "w") as f:
        json.dump(graph_data, f, indent=2)
    print(f"✅ Saved JSON adjacency: {json_file}")

    # 3. Human-readable searchable format
    searchable_file = f"{base_name}_searchable.json"
    searchable_data = {
        "metadata": {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "graph_type": "bike_routing",
            "transport_mode": "bike",
        },
        "stations": {},
        "connections": {},
    }

    # Add station data
    for node_id, node_data in graph.nodes(data=True):
        searchable_data["stations"][node_id] = {
            "name": node_data.get("name", ""),
            "lat": node_data.get("lat", 0),
            "lon": node_data.get("lon", 0),
            "lines": node_data.get("lines", []),
            "zone": node_data.get("zone", ""),
            "connections": len(list(graph.neighbors(node_id))),
        }

    # Add connection data with station names for readability
    for station1, station2, edge_data in graph.edges(data=True):
        station1_name = graph.nodes[station1].get("name", station1)
        station2_name = graph.nodes[station2].get("name", station2)

        connection_key = f"{station1_name} ↔ {station2_name}"
        searchable_data["connections"][connection_key] = {
            "station1_id": station1,
            "station2_id": station2,
            "station1_name": station1_name,
            "station2_name": station2_name,
            "duration_minutes": edge_data.get("duration_minutes", 0),
            "transport_mode": edge_data.get("transport_mode", "bike"),
        }

    with open(searchable_file, "w") as f:
        json.dump(searchable_data, f, indent=2)
    print(f"✅ Saved searchable JSON: {searchable_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Build NetworkX graph of bike routes between TfL stations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start fresh build
  python build_bike_graph.py

  # Continue from previous progress
  python build_bike_graph.py --continue

  # Retry failed connections from previous run
  python build_bike_graph.py --continue --retry-failed

  # Test with limited pairs
  python build_bike_graph.py --max-pairs 100
        """,
    )

    parser.add_argument(
        "--continue",
        action="store_true",
        dest="continue_build",
        help="Continue from previous progress",
    )
    parser.add_argument(
        "--retry-failed", action="store_true", help="Retry previously failed connections"
    )
    parser.add_argument(
        "--progress-file",
        default="bike_graph_progress.json",
        help="Progress file to save/load (default: bike_graph_progress.json)",
    )
    parser.add_argument(
        "--max-pairs", type=int, help="Maximum number of pairs to process (for testing)"
    )
    parser.add_argument(
        "--output", default="bike_graph", help="Base name for output files (default: bike_graph)"
    )

    args = parser.parse_args()

    # Build the graph
    G = build_bike_graph(
        continue_build=args.continue_build,
        retry_failed=args.retry_failed,
        progress_file=args.progress_file,
        max_pairs=args.max_pairs,
        output_name=args.output,
    )

    # Save in multiple formats
    save_graph_formats(G, args.output)

    print("\n🎉 Bike graph build complete!")
    print(f"📊 Final graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")


if __name__ == "__main__":
    main()
