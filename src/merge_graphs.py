#!/usr/bin/env python3
"""
ABOUTME: Merge TfL tube graph and bike graph into unified routing network
ABOUTME: Creates combined NetworkX graph with standardized edge attributes for multi-modal routing
"""

import argparse
import json
import pickle
import sys
from pathlib import Path

import networkx as nx


def load_tfl_graph(tfl_graph_file: str = "tfl_graph.pickle") -> nx.Graph:
    """Load TfL tube graph from pickle file."""
    print(f"Loading TfL graph from {tfl_graph_file}...")

    try:
        with open(tfl_graph_file, "rb") as f:
            tfl_graph = pickle.load(f)

        print(
            f"✅ Loaded TfL graph: {tfl_graph.number_of_nodes()} nodes, {tfl_graph.number_of_edges()} edges"
        )
        return tfl_graph

    except FileNotFoundError:
        print(f"❌ TfL graph file not found: {tfl_graph_file}")
        print("   Run build_tfl_graph.py first to create the tube network")
        sys.exit(1)


def load_bike_graph(bike_graph_file: str = "bike_graph.pickle") -> nx.Graph:
    """Load bike routing graph from pickle file."""
    print(f"Loading bike graph from {bike_graph_file}...")

    try:
        with open(bike_graph_file, "rb") as f:
            bike_graph = pickle.load(f)

        print(
            f"✅ Loaded bike graph: {bike_graph.number_of_nodes()} nodes, {bike_graph.number_of_edges()} edges"
        )
        return bike_graph

    except FileNotFoundError:
        print(f"❌ Bike graph file not found: {bike_graph_file}")
        print("   Run build_bike_graph.py first to create the bike network")
        sys.exit(1)


def merge_graphs(tfl_graph: nx.Graph, bike_graph: nx.Graph) -> nx.Graph:
    """
    Merge TfL and bike graphs with standardized edge attributes.

    Returns:
        Unified graph with consistent edge attributes:
        - duration_minutes: Travel time
        - transport_mode: 'tube' or 'bike'
        - distance_km: Distance (bike only)
        - line: Tube line name (tube only)
    """
    print("\nMerging graphs...")

    # Create new graph with all nodes
    merged_graph = nx.Graph()

    # Add all nodes (should be the same 272 stations in both graphs)
    for node, data in tfl_graph.nodes(data=True):
        merged_graph.add_node(node, **data)

    print(f"📊 Added {merged_graph.number_of_nodes()} station nodes")

    # Add TfL tube edges with standardized attributes
    tube_edges_added = 0
    for station1, station2, data in tfl_graph.edges(data=True):
        # TfL graph uses 'weight' for duration
        duration = data.get("weight", 0)

        # Try to get line information if available
        line = data.get("line", "unknown")

        merged_graph.add_edge(
            station1,
            station2,
            duration_minutes=float(duration),
            transport_mode="tube",
            line=line,
            distance_km=None,  # Not available for tube
        )
        tube_edges_added += 1

    print(f"🚇 Added {tube_edges_added} tube edges")

    # Add bike edges with standardized attributes
    bike_edges_added = 0
    for station1, station2, data in bike_graph.edges(data=True):
        # Bike graph already uses 'duration_minutes'
        duration = data.get("duration_minutes", 0)
        distance = data.get("distance_km", None)

        # Check if edge already exists (shouldn't happen but be safe)
        if merged_graph.has_edge(station1, station2):
            # Keep the faster option
            existing_duration = merged_graph[station1][station2]["duration_minutes"]
            if duration < existing_duration:
                merged_graph[station1][station2].update(
                    {
                        "duration_minutes": float(duration),
                        "transport_mode": "bike",
                        "distance_km": distance,
                        "line": None,
                    }
                )
        else:
            merged_graph.add_edge(
                station1,
                station2,
                duration_minutes=float(duration),
                transport_mode="bike",
                distance_km=distance,
                line=None,
            )
            bike_edges_added += 1

    print(f"🚴 Added {bike_edges_added} bike edges")
    print(
        f"📊 Total merged graph: {merged_graph.number_of_nodes()} nodes, {merged_graph.number_of_edges()} edges"
    )

    return merged_graph


def save_merged_graph(graph: nx.Graph, base_name: str = "merged_graph"):
    """Save merged graph in multiple formats."""
    print("\n💾 Saving merged graph...")

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
            "tube_edges": sum(
                1 for _, _, d in graph.edges(data=True) if d.get("transport_mode") == "tube"
            ),
            "bike_edges": sum(
                1 for _, _, d in graph.edges(data=True) if d.get("transport_mode") == "bike"
            ),
            "graph_type": "multi_modal_routing",
        },
        "stations": {},
        "connections": {},
    }

    # Add station data
    for node_id, node_data in graph.nodes(data=True):
        tube_connections = sum(
            1 for _, _, d in graph.edges(node_id, data=True) if d.get("transport_mode") == "tube"
        )
        bike_connections = sum(
            1 for _, _, d in graph.edges(node_id, data=True) if d.get("transport_mode") == "bike"
        )

        searchable_data["stations"][node_id] = {
            "name": node_data.get("name", ""),
            "lat": node_data.get("lat", 0),
            "lon": node_data.get("lon", 0),
            "lines": node_data.get("lines", []),
            "zone": node_data.get("zone", ""),
            "tube_connections": tube_connections,
            "bike_connections": bike_connections,
            "total_connections": len(list(graph.neighbors(node_id))),
        }

    # Add connection data with station names for readability
    for station1, station2, edge_data in graph.edges(data=True):
        station1_name = graph.nodes[station1].get("name", station1)
        station2_name = graph.nodes[station2].get("name", station2)

        mode = edge_data.get("transport_mode", "unknown")
        connection_key = f"{station1_name} ↔ {station2_name} ({mode})"

        searchable_data["connections"][connection_key] = {
            "station1_id": station1,
            "station2_id": station2,
            "station1_name": station1_name,
            "station2_name": station2_name,
            "duration_minutes": edge_data.get("duration_minutes", 0),
            "transport_mode": mode,
            "distance_km": edge_data.get("distance_km"),
            "line": edge_data.get("line"),
        }

    with open(searchable_file, "w") as f:
        json.dump(searchable_data, f, indent=2)
    print(f"✅ Saved searchable JSON: {searchable_file}")


def analyze_merged_graph(graph: nx.Graph):
    """Analyze and display statistics about the merged graph."""
    print("\n📊 MERGED GRAPH ANALYSIS")
    print("=" * 50)

    # Count edges by type
    tube_edges = [
        (u, v, d) for u, v, d in graph.edges(data=True) if d.get("transport_mode") == "tube"
    ]
    bike_edges = [
        (u, v, d) for u, v, d in graph.edges(data=True) if d.get("transport_mode") == "bike"
    ]

    print(f"Total edges: {graph.number_of_edges()}")
    print(f"  - Tube edges: {len(tube_edges)}")
    print(f"  - Bike edges: {len(bike_edges)}")

    # Average durations
    if tube_edges:
        avg_tube_duration = sum(d["duration_minutes"] for _, _, d in tube_edges) / len(tube_edges)
        print(f"\nAverage tube journey: {avg_tube_duration:.1f} minutes")

    if bike_edges:
        avg_bike_duration = sum(d["duration_minutes"] for _, _, d in bike_edges) / len(bike_edges)
        print(f"Average bike journey: {avg_bike_duration:.1f} minutes")

    # Connectivity check
    if nx.is_connected(graph):
        print("\n✅ Graph is fully connected - all stations reachable")
    else:
        components = list(nx.connected_components(graph))
        print(f"\n⚠️  Graph has {len(components)} disconnected components")

    # Sample connections
    print("\n📍 Sample connections:")
    sample_edges = list(graph.edges(data=True))[:5]
    for u, v, d in sample_edges:
        u_name = graph.nodes[u].get("name", u)[:30]
        v_name = graph.nodes[v].get("name", v)[:30]
        mode = d.get("transport_mode", "unknown")
        duration = d.get("duration_minutes", 0)
        print(f"  {u_name} → {v_name}: {duration:.1f} min ({mode})")


def main():
    parser = argparse.ArgumentParser(
        description="Merge TfL tube and bike graphs into unified routing network",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge with default file names
  python merge_graphs.py

  # Use custom file names
  python merge_graphs.py --tfl-graph my_tfl.pickle --bike-graph my_bike.pickle

  # Custom output name
  python merge_graphs.py --output unified_graph
        """,
    )

    parser.add_argument(
        "--tfl-graph",
        default="tfl_graph.pickle",
        help="TfL graph pickle file (default: tfl_graph.pickle)",
    )
    parser.add_argument(
        "--bike-graph",
        default="bike_graph.pickle",
        help="Bike graph pickle file (default: bike_graph.pickle)",
    )
    parser.add_argument(
        "--output",
        default="merged_graph",
        help="Base name for output files (default: merged_graph)",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Show detailed analysis of merged graph",
    )

    args = parser.parse_args()

    # Load both graphs
    tfl_graph = load_tfl_graph(args.tfl_graph)
    bike_graph = load_bike_graph(args.bike_graph)

    # Merge graphs
    merged_graph = merge_graphs(tfl_graph, bike_graph)

    # Save merged graph
    save_merged_graph(merged_graph, args.output)

    # Analyze if requested
    if args.analyze:
        analyze_merged_graph(merged_graph)

    print("\n🎉 Graph merging complete!")


if __name__ == "__main__":
    main()
