#!/usr/bin/env python3
"""
ABOUTME: Build multi-layer TfL graph with line-specific nodes and line change edges
ABOUTME: Transforms station nodes into (station, line) pairs to model line changes accurately
"""

import argparse
import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import networkx as nx

from routing_config import LINE_CHANGE_TIME_MINUTES


def load_tfl_graph(graph_file: str = "tfl_graph.pickle") -> nx.Graph:
    """Load the original TfL graph."""
    print(f"Loading TfL graph from {graph_file}...")
    try:
        with open(graph_file, "rb") as f:
            graph = pickle.load(f)
        print(f"✅ Loaded: {graph.number_of_nodes()} stations, {graph.number_of_edges()} edges")
        return graph
    except FileNotFoundError:
        print(f"❌ Graph file not found: {graph_file}")
        print("   Run build_tfl_graph.py first")
        sys.exit(1)


def load_station_data(stations_file: str = "tfl_stations.json") -> dict:
    """Load station data to get line information."""
    print(f"Loading station data from {stations_file}...")
    try:
        with open(stations_file) as f:
            data = json.load(f)
        return data["stations"]
    except FileNotFoundError:
        print(f"❌ Station data file not found: {stations_file}")
        sys.exit(1)


def build_station_connections_map(stations_data: dict) -> dict:
    """
    Build a map of line-specific connections from TfL station data.

    Returns:
        Dict mapping (station1_id, station2_id, line) -> duration_minutes
    """
    connections = {}

    for station_id, station_info in stations_data.items():
        station_connections = station_info.get("connections", [])

        for connection in station_connections:
            to_station = connection["to_station"]
            line = connection["line"]

            # Create bidirectional connections (TfL data might be unidirectional)
            # We'll store as a tuple that can be looked up in either direction
            key1 = (station_id, to_station, line)
            key2 = (to_station, station_id, line)

            # We don't have duration from connection data, will estimate later
            connections[key1] = None
            connections[key2] = None

    return connections


def build_multilayer_graph(original_graph: nx.Graph, stations_data: dict) -> nx.Graph:
    """
    Build multi-layer graph with line-specific nodes using accurate TfL connection data.

    Args:
        original_graph: Original TfL graph with stations as nodes (used for duration estimates)
        stations_data: Station information including lines and line-specific connections

    Returns:
        Multi-layer graph with (station, line) nodes
    """
    print("\nBuilding multi-layer graph...")

    multilayer = nx.Graph()

    # Statistics
    line_specific_nodes = 0
    travel_edges = 0
    line_change_edges = 0

    # Step 1: Create line-specific nodes
    print("\n1. Creating line-specific nodes...")
    station_line_nodes = defaultdict(list)  # station_id -> list of line-specific nodes

    for station_id, station_info in stations_data.items():
        if station_id not in original_graph:
            continue

        lines = station_info.get("lines", [])
        if not lines:
            print(f"⚠️  Station {station_info['name']} has no lines")
            continue

        for line in lines:
            # Skip duplicate Circle/H&C nodes
            if line == "hammersmith-city" and "circle" in lines:
                continue

            node_id = f"{station_id}_{line}"
            multilayer.add_node(
                node_id,
                station_id=station_id,
                station_name=station_info["name"],
                line=line,
                lat=station_info["lat"],
                lon=station_info["lon"],
                zone=station_info.get("zone", ""),
                original_lines=lines,
            )
            station_line_nodes[station_id].append(node_id)
            line_specific_nodes += 1

    print(
        f"✅ Created {line_specific_nodes} line-specific nodes from {len(station_line_nodes)} stations"
    )

    # Step 2: Build connection map from TfL data
    print("\n2. Building line-specific connection map from TfL data...")
    connection_map = build_station_connections_map(stations_data)
    print(f"✅ Found {len(connection_map)} line-specific connections")

    # Step 3: Add travel edges using line-specific connections
    print("\n3. Adding travel edges using accurate line data...")
    edges_added = 0
    edges_with_duration = 0

    for station_id, station_info in stations_data.items():
        station_connections = station_info.get("connections", [])

        for connection in station_connections:
            to_station_id = connection["to_station"]
            line = connection["line"]

            # Skip Circle/H&C consolidation
            if line == "hammersmith-city" and "circle" in stations_data.get(station_id, {}).get(
                "lines", []
            ):
                continue

            # Create line-specific nodes
            node1 = f"{station_id}_{line}"
            node2 = f"{to_station_id}_{line}"

            # Only add if both nodes exist in our multilayer graph
            if node1 in multilayer and node2 in multilayer:
                # Don't add duplicate edges
                if not multilayer.has_edge(node1, node2):
                    # Try to get duration from original graph
                    duration = 2.0  # Default fallback
                    if original_graph.has_edge(station_id, to_station_id):
                        duration = original_graph[station_id][to_station_id].get("weight", 2.0)
                        edges_with_duration += 1

                    multilayer.add_edge(
                        node1,
                        node2,
                        duration_minutes=float(duration),
                        transport_mode="tube",
                        line=line,
                        edge_type="travel",
                    )
                    edges_added += 1

    travel_edges = edges_added
    print(
        f"✅ Added {travel_edges} travel edges ({edges_with_duration} with original durations, {travel_edges - edges_with_duration} with fallback)"
    )

    # Step 3: Add line change edges within stations
    print(f"\n3. Adding line change edges (weight: {LINE_CHANGE_TIME_MINUTES} minutes)...")

    for station_id, line_nodes in station_line_nodes.items():
        if len(line_nodes) < 2:
            continue

        station_name = stations_data[station_id]["name"]

        # Connect all pairs of lines at this station
        for i in range(len(line_nodes)):
            for j in range(i + 1, len(line_nodes)):
                node1 = line_nodes[i]
                node2 = line_nodes[j]

                # Extract line names from node IDs
                line1 = node1.split("_")[-1]
                line2 = node2.split("_")[-1]

                multilayer.add_edge(
                    node1,
                    node2,
                    duration_minutes=float(LINE_CHANGE_TIME_MINUTES),
                    transport_mode="line_change",
                    from_line=line1,
                    to_line=line2,
                    station_name=station_name,
                    edge_type="line_change",
                )
                line_change_edges += 1

    print(f"✅ Added {line_change_edges} line change edges")

    # Summary
    print("\n=== MULTI-LAYER GRAPH SUMMARY ===")
    print(f"📊 Total nodes: {multilayer.number_of_nodes()} (from {len(stations_data)} stations)")
    print(f"📊 Total edges: {multilayer.number_of_edges()}")
    print(f"   - Travel edges: {travel_edges}")
    print(f"   - Line change edges: {line_change_edges}")
    print(f"📊 Average lines per station: {line_specific_nodes / len(station_line_nodes):.1f}")

    return multilayer


def save_graph_formats(graph: nx.Graph, base_name: str = "tfl_multilayer_graph"):
    """Save graph in multiple formats."""
    print("\n💾 Saving multi-layer graph...")

    # 1. NetworkX pickle
    pickle_file = f"{base_name}.pickle"
    with open(pickle_file, "wb") as f:
        pickle.dump(graph, f)
    print(f"✅ Saved NetworkX pickle: {pickle_file}")

    # 2. Searchable JSON format
    searchable_file = f"{base_name}_searchable.json"
    searchable_data = {
        "metadata": {
            "total_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
            "graph_type": "multilayer_tfl",
            "line_change_penalty_minutes": LINE_CHANGE_TIME_MINUTES,
        },
        "nodes": {},
        "travel_edges": [],
        "line_change_edges": [],
    }

    # Add nodes
    for node_id, node_data in graph.nodes(data=True):
        searchable_data["nodes"][node_id] = {
            "station_id": node_data.get("station_id"),
            "station_name": node_data.get("station_name"),
            "line": node_data.get("line"),
            "lat": node_data.get("lat"),
            "lon": node_data.get("lon"),
            "zone": node_data.get("zone"),
        }

    # Add edges by type
    for node1, node2, edge_data in graph.edges(data=True):
        edge_info = {
            "from": node1,
            "to": node2,
            "duration_minutes": edge_data.get("duration_minutes"),
        }

        if edge_data.get("edge_type") == "line_change":
            edge_info["from_line"] = edge_data.get("from_line")
            edge_info["to_line"] = edge_data.get("to_line")
            edge_info["station_name"] = edge_data.get("station_name")
            searchable_data["line_change_edges"].append(edge_info)
        else:
            edge_info["line"] = edge_data.get("line")
            searchable_data["travel_edges"].append(edge_info)

    with open(searchable_file, "w") as f:
        json.dump(searchable_data, f, indent=2)
    print(f"✅ Saved searchable JSON: {searchable_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Build multi-layer TfL graph with line-specific nodes"
    )
    parser.add_argument(
        "--tfl-graph",
        default="tfl_graph.pickle",
        help="Input TfL graph file (default: tfl_graph.pickle)",
    )
    parser.add_argument(
        "--stations",
        default="tfl_stations.json",
        help="Station data file (default: tfl_stations.json)",
    )
    parser.add_argument(
        "--output",
        default="tfl_multilayer_graph",
        help="Output base name (default: tfl_multilayer_graph)",
    )

    args = parser.parse_args()

    # Load data
    original_graph = load_tfl_graph(args.tfl_graph)
    stations_data = load_station_data(args.stations)

    # Build multi-layer graph
    multilayer_graph = build_multilayer_graph(original_graph, stations_data)

    # Save in multiple formats
    save_graph_formats(multilayer_graph, args.output)

    print("\n🎉 Multi-layer TfL graph complete!")


if __name__ == "__main__":
    main()
