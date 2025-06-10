#!/usr/bin/env python3
"""
ABOUTME: Build multi-layer bike graph with line-specific nodes from original bike graph
ABOUTME: Expands bike edges to connect all line variants between stations
"""

import argparse
import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import networkx as nx


def load_bike_graph(graph_file: str = "bike_graph.pickle") -> nx.Graph:
    """Load the original bike graph."""
    print(f"Loading bike graph from {graph_file}...")
    try:
        with open(graph_file, "rb") as f:
            graph = pickle.load(f)
        print(
            f"✅ Loaded: {graph.number_of_nodes()} stations, {graph.number_of_edges()} bike edges"
        )
        return graph
    except FileNotFoundError:
        print(f"❌ Graph file not found: {graph_file}")
        print("   Run build_bike_graph.py first")
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


def build_multilayer_bike_graph(original_graph: nx.Graph, stations_data: dict) -> nx.Graph:
    """
    Build multi-layer bike graph with line-specific nodes.

    Args:
        original_graph: Original bike graph with stations as nodes
        stations_data: Station information including lines served

    Returns:
        Multi-layer graph with (station, line) nodes for bike edges
    """
    print("\nBuilding multi-layer bike graph...")

    multilayer = nx.Graph()

    # Statistics
    original_edges = 0
    expanded_edges = 0
    expansion_examples = []
    edges_by_expansion = defaultdict(int)

    # First, add all line-specific nodes (matching TfL multi-layer graph)
    print("\n1. Creating line-specific nodes...")
    line_specific_nodes = 0

    for station_id, station_info in stations_data.items():
        if station_id not in original_graph:
            continue

        lines = station_info.get("lines", [])
        if not lines:
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
            line_specific_nodes += 1

    print(f"✅ Created {line_specific_nodes} line-specific nodes")

    # Process each bike edge and expand to all line combinations
    print("\n2. Expanding bike edges to all line combinations...")

    for station1_id, station2_id, edge_data in original_graph.edges(data=True):
        original_edges += 1

        station1_lines = stations_data.get(station1_id, {}).get("lines", [])
        station2_lines = stations_data.get(station2_id, {}).get("lines", [])

        # Skip if either station has no lines
        if not station1_lines or not station2_lines:
            continue

        # Filter out H&C if Circle exists
        if "circle" in station1_lines and "hammersmith-city" in station1_lines:
            station1_lines = [line for line in station1_lines if line != "hammersmith-city"]
        if "circle" in station2_lines and "hammersmith-city" in station2_lines:
            station2_lines = [line for line in station2_lines if line != "hammersmith-city"]

        # Count edges for this station pair
        edge_count = 0

        # Create edges for all line combinations
        for line1 in station1_lines:
            for line2 in station2_lines:
                node1 = f"{station1_id}_{line1}"
                node2 = f"{station2_id}_{line2}"

                # Copy all edge attributes
                edge_attrs = edge_data.copy()

                # Ensure required attributes
                if "duration_minutes" not in edge_attrs and "weight" in edge_attrs:
                    edge_attrs["duration_minutes"] = edge_attrs["weight"]

                multilayer.add_edge(node1, node2, **edge_attrs)
                edge_count += 1
                expanded_edges += 1

        # Track expansion statistics
        edges_by_expansion[edge_count] += 1

        # Collect examples of high expansion
        if edge_count >= 12 and len(expansion_examples) < 5:
            expansion_examples.append(
                {
                    "from": stations_data[station1_id]["name"],
                    "to": stations_data[station2_id]["name"],
                    "from_lines": len(station1_lines),
                    "to_lines": len(station2_lines),
                    "edges_created": edge_count,
                }
            )

        # Progress update
        if original_edges % 1000 == 0:
            print(
                f"   Processed {original_edges:,} edges → {expanded_edges:,} multi-layer edges..."
            )

    print(f"✅ Expanded {original_edges:,} original edges to {expanded_edges:,} multi-layer edges")

    # Summary statistics
    print("\n=== EXPANSION STATISTICS ===")
    print(f"📊 Average expansion factor: {expanded_edges / original_edges:.1f}x")
    print(f"📊 Total nodes: {multilayer.number_of_nodes()}")
    print(f"📊 Total edges: {multilayer.number_of_edges()}")

    print("\n📊 Edge expansion distribution:")
    for expansion, count in sorted(edges_by_expansion.items()):
        print(f"   {expansion} edges created: {count} station pairs")

    if expansion_examples:
        print("\n📊 Examples of high expansion:")
        for ex in expansion_examples:
            print(
                f"   {ex['from']} ({ex['from_lines']} lines) → "
                f"{ex['to']} ({ex['to_lines']} lines): "
                f"{ex['edges_created']} edges"
            )

    return multilayer


def save_graph_formats(graph: nx.Graph, base_name: str = "bike_multilayer_graph"):
    """Save graph in multiple formats."""
    print("\n💾 Saving multi-layer bike graph...")

    # 1. NetworkX pickle
    pickle_file = f"{base_name}.pickle"
    with open(pickle_file, "wb") as f:
        pickle.dump(graph, f)
    print(f"✅ Saved NetworkX pickle: {pickle_file}")

    # 2. Searchable JSON format (compact version due to size)
    searchable_file = f"{base_name}_searchable.json"
    searchable_data = {
        "metadata": {
            "total_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
            "graph_type": "multilayer_bike",
            "note": "Bike edges expanded for all line combinations",
        },
        "sample_nodes": {},
        "sample_edges": [],
    }

    # Add sample of nodes (first 10)
    for i, (node_id, node_data) in enumerate(graph.nodes(data=True)):
        if i >= 10:
            break
        searchable_data["sample_nodes"][node_id] = {
            "station_id": node_data.get("station_id"),
            "station_name": node_data.get("station_name"),
            "line": node_data.get("line"),
        }

    # Add sample of edges (first 10)
    for i, (node1, node2, edge_data) in enumerate(graph.edges(data=True)):
        if i >= 10:
            break
        searchable_data["sample_edges"].append(
            {
                "from": node1,
                "to": node2,
                "duration_minutes": edge_data.get("duration_minutes"),
                "transport_mode": edge_data.get("transport_mode"),
            }
        )

    with open(searchable_file, "w") as f:
        json.dump(searchable_data, f, indent=2)
    print(f"✅ Saved searchable JSON (compact): {searchable_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Build multi-layer bike graph with line-specific nodes"
    )
    parser.add_argument(
        "--bike-graph",
        default="bike_graph.pickle",
        help="Input bike graph file (default: bike_graph.pickle)",
    )
    parser.add_argument(
        "--stations",
        default="tfl_stations.json",
        help="Station data file (default: tfl_stations.json)",
    )
    parser.add_argument(
        "--output",
        default="bike_multilayer_graph",
        help="Output base name (default: bike_multilayer_graph)",
    )

    args = parser.parse_args()

    # Load data
    original_graph = load_bike_graph(args.bike_graph)
    stations_data = load_station_data(args.stations)

    # Build multi-layer graph
    multilayer_graph = build_multilayer_bike_graph(original_graph, stations_data)

    # Save in multiple formats
    save_graph_formats(multilayer_graph, args.output)

    print("\n🎉 Multi-layer bike graph complete!")


if __name__ == "__main__":
    main()
