#!/usr/bin/env python3
"""
ABOUTME: Merge multi-layer TfL tube graph and bike graph into unified routing network
ABOUTME: Creates combined NetworkX graph with line-specific nodes for accurate multi-modal routing
"""

import argparse
import json
import pickle
import sys
from pathlib import Path

import networkx as nx


def load_graph(graph_file: str, graph_type: str) -> nx.Graph:
    """Load a graph from pickle file."""
    print(f"Loading {graph_type} graph from {graph_file}...")

    try:
        with open(graph_file, "rb") as f:
            graph = pickle.load(f)

        print(
            f"✅ Loaded {graph_type} graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges"
        )
        return graph

    except FileNotFoundError:
        print(f"❌ {graph_type} graph file not found: {graph_file}")
        sys.exit(1)


def merge_multilayer_graphs(tfl_graph: nx.Graph, bike_graph: nx.Graph) -> nx.Graph:
    """
    Merge multi-layer TfL and bike graphs.

    Both graphs should have line-specific nodes (e.g., 940GZZLUBST_jubilee).

    Returns:
        Unified graph with all nodes and edges from both graphs
    """
    print("\nMerging multi-layer graphs...")

    # Create new graph
    merged_graph = nx.Graph()

    # Add all nodes from TfL graph (includes line-specific attributes)
    print("\n1. Adding nodes...")
    for node, data in tfl_graph.nodes(data=True):
        merged_graph.add_node(node, **data)

    # Verify bike graph has same nodes
    bike_nodes = set(bike_graph.nodes())
    tfl_nodes = set(tfl_graph.nodes())

    if bike_nodes != tfl_nodes:
        print(f"⚠️  Node mismatch: TfL has {len(tfl_nodes)}, Bike has {len(bike_nodes)}")
        missing_in_bike = tfl_nodes - bike_nodes
        missing_in_tfl = bike_nodes - tfl_nodes

        if missing_in_bike:
            print(f"   Missing in bike graph: {list(missing_in_bike)[:5]}...")
        if missing_in_tfl:
            print(f"   Missing in TfL graph: {list(missing_in_tfl)[:5]}...")
    else:
        print(f"✅ Both graphs have identical {len(tfl_nodes)} nodes")

    # Add TfL edges (tube travel and line changes)
    print("\n2. Adding TfL edges...")
    tube_travel_edges = 0
    line_change_edges = 0

    for station1, station2, data in tfl_graph.edges(data=True):
        edge_type = data.get("edge_type", "travel")

        if edge_type == "line_change":
            line_change_edges += 1
        else:
            tube_travel_edges += 1

        # Add edge with all attributes
        merged_graph.add_edge(station1, station2, **data)

    print(f"✅ Added {tube_travel_edges} tube travel edges")
    print(f"✅ Added {line_change_edges} line change edges")

    # Add bike edges
    print("\n3. Adding bike edges...")
    bike_edges_added = 0
    bike_edges_skipped = 0

    for station1, station2, data in bike_graph.edges(data=True):
        # Check if edge already exists (shouldn't happen between different modes)
        if merged_graph.has_edge(station1, station2):
            # This would be unusual - same line-specific nodes connected by both tube and bike
            bike_edges_skipped += 1
            existing_mode = merged_graph[station1][station2].get("transport_mode", "unknown")
            print(f"⚠️  Edge already exists: {station1} ↔ {station2} ({existing_mode})")
        else:
            merged_graph.add_edge(station1, station2, **data)
            bike_edges_added += 1

    print(f"✅ Added {bike_edges_added} bike edges")
    if bike_edges_skipped:
        print(f"⚠️  Skipped {bike_edges_skipped} duplicate edges")

    print(
        f"\n📊 Total merged graph: {merged_graph.number_of_nodes()} nodes, {merged_graph.number_of_edges()} edges"
    )

    return merged_graph


def save_merged_graph(graph: nx.Graph, base_name: str = "merged_multilayer_graph"):
    """Save merged multi-layer graph in multiple formats."""
    print("\n💾 Saving merged multi-layer graph...")

    # 1. NetworkX pickle (fastest loading)
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
            "tube_travel_edges": sum(
                1
                for _, _, d in graph.edges(data=True)
                if d.get("transport_mode") == "tube" and d.get("edge_type") != "line_change"
            ),
            "line_change_edges": sum(
                1 for _, _, d in graph.edges(data=True) if d.get("edge_type") == "line_change"
            ),
            "bike_edges": sum(
                1 for _, _, d in graph.edges(data=True) if d.get("transport_mode") == "bike"
            ),
            "graph_type": "multi_layer_multi_modal",
        },
        "sample_nodes": {},
        "edge_summary": {},
    }

    # Add sample nodes
    for i, (node_id, node_data) in enumerate(graph.nodes(data=True)):
        if i >= 10:
            break
        searchable_data["sample_nodes"][node_id] = {
            "station_id": node_data.get("station_id"),
            "station_name": node_data.get("station_name"),
            "line": node_data.get("line"),
            "lat": node_data.get("lat"),
            "lon": node_data.get("lon"),
        }

    # Summarize edges by type
    edge_types = {"tube_travel": [], "line_change": [], "bike": []}

    for u, v, d in list(graph.edges(data=True))[:30]:  # First 30 edges as samples
        if d.get("edge_type") == "line_change":
            edge_types["line_change"].append(
                {
                    "from": u,
                    "to": v,
                    "duration_minutes": d.get("duration_minutes"),
                    "from_line": d.get("from_line"),
                    "to_line": d.get("to_line"),
                }
            )
        elif d.get("transport_mode") == "tube":
            edge_types["tube_travel"].append(
                {
                    "from": u,
                    "to": v,
                    "duration_minutes": d.get("duration_minutes"),
                    "line": d.get("line"),
                }
            )
        elif d.get("transport_mode") == "bike":
            edge_types["bike"].append(
                {"from": u, "to": v, "duration_minutes": d.get("duration_minutes")}
            )

    searchable_data["edge_summary"] = {
        "tube_travel_samples": edge_types["tube_travel"][:5],
        "line_change_samples": edge_types["line_change"][:5],
        "bike_samples": edge_types["bike"][:5],
    }

    with open(searchable_file, "w") as f:
        json.dump(searchable_data, f, indent=2)
    print(f"✅ Saved searchable JSON: {searchable_file}")


def analyze_merged_graph(graph: nx.Graph):
    """Analyze and display statistics about the merged multi-layer graph."""
    print("\n📊 MERGED MULTI-LAYER GRAPH ANALYSIS")
    print("=" * 60)

    # Count nodes by line
    lines_count = {}
    stations_count = set()

    for node_id, node_data in graph.nodes(data=True):
        line = node_data.get("line", "unknown")
        lines_count[line] = lines_count.get(line, 0) + 1
        stations_count.add(node_data.get("station_id", node_id))

    print(f"Total nodes: {graph.number_of_nodes()}")
    print(f"Unique stations: {len(stations_count)}")
    print("\nNodes per line:")
    for line, count in sorted(lines_count.items()):
        print(f"  - {line}: {count} nodes")

    # Count edges by type
    edge_stats = {"tube_travel": 0, "line_change": 0, "bike": 0}

    for _, _, data in graph.edges(data=True):
        if data.get("edge_type") == "line_change":
            edge_stats["line_change"] += 1
        elif data.get("transport_mode") == "tube":
            edge_stats["tube_travel"] += 1
        elif data.get("transport_mode") == "bike":
            edge_stats["bike"] += 1

    print(f"\nTotal edges: {graph.number_of_edges()}")
    print(f"  - Tube travel edges: {edge_stats['tube_travel']}")
    print(f"  - Line change edges: {edge_stats['line_change']}")
    print(f"  - Bike edges: {edge_stats['bike']}")

    # Average durations by type
    durations = {"tube_travel": [], "line_change": [], "bike": []}

    for _, _, data in graph.edges(data=True):
        duration = data.get("duration_minutes", 0)
        if data.get("edge_type") == "line_change":
            durations["line_change"].append(duration)
        elif data.get("transport_mode") == "tube":
            durations["tube_travel"].append(duration)
        elif data.get("transport_mode") == "bike":
            durations["bike"].append(duration)

    print("\nAverage durations:")
    for edge_type, times in durations.items():
        if times:
            avg_time = sum(times) / len(times)
            print(f"  - {edge_type}: {avg_time:.1f} minutes")

    # Connectivity check
    if nx.is_connected(graph):
        print("\n✅ Graph is fully connected - all nodes reachable")
    else:
        components = list(nx.connected_components(graph))
        print(f"\n⚠️  Graph has {len(components)} disconnected components")
        largest = max(components, key=len)
        print(f"   Largest component: {len(largest)} nodes")

    # Sample multi-modal path potential
    print("\n📍 Example multi-line stations (high connectivity):")
    node_connections = []
    for node, data in graph.nodes(data=True):
        degree = graph.degree(node)
        node_connections.append((degree, node, data.get("station_name", ""), data.get("line", "")))

    node_connections.sort(reverse=True)
    for degree, _node, name, line in node_connections[:5]:
        print(f"  {name} ({line}): {degree} connections")


def main():
    parser = argparse.ArgumentParser(
        description="Merge multi-layer TfL tube and bike graphs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge multi-layer graphs
  python merge_multilayer_graphs.py

  # Use specific files
  python merge_multilayer_graphs.py --tfl tfl_multilayer_graph.pickle --bike bike_multilayer_graph.pickle

  # Custom output name
  python merge_multilayer_graphs.py --output merged_ml_graph
        """,
    )

    parser.add_argument(
        "--tfl",
        default="tfl_multilayer_graph.pickle",
        help="Multi-layer TfL graph file (default: tfl_multilayer_graph.pickle)",
    )
    parser.add_argument(
        "--bike",
        default="bike_multilayer_graph.pickle",
        help="Multi-layer bike graph file (default: bike_multilayer_graph.pickle)",
    )
    parser.add_argument(
        "--output",
        default="merged_multilayer_graph",
        help="Base name for output files (default: merged_multilayer_graph)",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Show detailed analysis of merged graph",
    )

    args = parser.parse_args()

    # Load both multi-layer graphs
    tfl_graph = load_graph(args.tfl, "TfL multi-layer")
    bike_graph = load_graph(args.bike, "Bike multi-layer")

    # Merge graphs
    merged_graph = merge_multilayer_graphs(tfl_graph, bike_graph)

    # Save merged graph
    save_merged_graph(merged_graph, args.output)

    # Analyze if requested
    if args.analyze:
        analyze_merged_graph(merged_graph)

    print("\n🎉 Multi-layer graph merging complete!")


if __name__ == "__main__":
    main()
