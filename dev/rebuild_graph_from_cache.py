#!/usr/bin/env python3
"""
ABOUTME: Rebuild bike graph from cached progress data
ABOUTME: Creates NetworkX graph with all edges from bike_time_cache in progress file
"""

import json
import pickle
from pathlib import Path

import networkx as nx


def rebuild_graph_from_cache():
    print("🔧 Rebuilding bike graph from cached data...")

    # Load progress file
    with open("bike_graph_progress.json") as f:
        progress_data = json.load(f)

    bike_time_cache = progress_data.get("bike_time_cache", {})
    print(f"📊 Found {len(bike_time_cache)} cached route pairs")

    # Load station data
    with open("tfl_stations.json") as f:
        stations_data = json.load(f)
    stations = stations_data["stations"]

    # Create graph
    G = nx.Graph()

    # Add all stations as nodes
    for station_id, station_data in stations.items():
        G.add_node(station_id, **station_data)
    print(f"📍 Added {G.number_of_nodes()} station nodes")

    # Add edges from cache
    successful_edges = 0
    failed_routes = 0

    for key, duration_minutes in bike_time_cache.items():
        station1_id, station2_id = key.split("|")

        if duration_minutes is not None and duration_minutes >= 0:
            # Add bidirectional edge
            G.add_edge(
                station1_id,
                station2_id,
                duration_minutes=duration_minutes,
                transport_mode="bike",
                distance_km=None,
            )
            successful_edges += 1
        else:
            failed_routes += 1

    print(f"✅ Added {successful_edges} edges from cached successful routes")
    print(f"❌ Skipped {failed_routes} failed routes (null values)")

    # Save the rebuilt graph
    with open("bike_graph.pickle", "wb") as f:
        pickle.dump(G, f)
    print("💾 Saved rebuilt graph to bike_graph.pickle")

    print("\n🎉 Graph rebuilt successfully!")
    print(f"📊 Final graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    return G


if __name__ == "__main__":
    rebuild_graph_from_cache()
