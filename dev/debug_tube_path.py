#!/usr/bin/env python3
"""
ABOUTME: Debug script to find and display tube-only paths between stations
ABOUTME: Uses Dijkstra's algorithm on the TfL graph to show intermediate stations
"""

import argparse
import pickle

import networkx as nx


def find_station_id(graph, station_name):
    """Find station ID by partial name match."""
    matches = []
    for node_id, data in graph.nodes(data=True):
        # Handle both regular and multi-layer graphs
        name = data.get("name", data.get("station_name", ""))
        if station_name.lower() in name.lower():
            matches.append((node_id, name))

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"\nMultiple matches for '{station_name}':")
        for i, (sid, name) in enumerate(matches):
            print(f"{i + 1}. {name} ({sid})")
        return None, None
    else:
        print(f"\nNo stations found matching '{station_name}'")
        return None, None


def main():
    parser = argparse.ArgumentParser(description="Debug tube paths between stations")
    parser.add_argument("from_station", help="Starting station name")
    parser.add_argument("to_station", help="Destination station name")
    parser.add_argument(
        "--graph", default="tfl_graph.pickle", help="Graph file to use (default: tfl_graph.pickle)"
    )

    args = parser.parse_args()

    # Load graph
    print(f"Loading graph from {args.graph}...")
    try:
        with open(args.graph, "rb") as f:
            graph = pickle.load(f)
        print(
            f"✅ Loaded: {graph.number_of_nodes()} stations, {graph.number_of_edges()} connections\n"
        )
    except FileNotFoundError:
        print(f"❌ Graph file not found: {args.graph}")
        return

    # Find station IDs
    from_id, from_name = find_station_id(graph, args.from_station)
    if not from_id:
        return

    to_id, to_name = find_station_id(graph, args.to_station)
    if not to_id:
        return

    print(f"\nFinding path from {from_name} to {to_name}...")
    print(f"Station IDs: {from_id} → {to_id}\n")

    # Check if stations are in the graph
    if from_id not in graph:
        print(f"❌ {from_name} not in graph")
        return
    if to_id not in graph:
        print(f"❌ {to_name} not in graph")
        return

    # Find shortest path
    try:
        path = nx.shortest_path(graph, from_id, to_id, weight="weight")

        print(f"Found path with {len(path)} stations:")
        print("=" * 60)

        total_time = 0
        for i in range(len(path)):
            station_data = graph.nodes[path[i]]
            station_name = station_data.get("name", path[i])
            lines = station_data.get("lines", [])

            print(f"\n{i + 1}. {station_name}")
            print(f"   Lines: {', '.join(lines)}")

            # Show edge to next station
            if i < len(path) - 1:
                edge_data = graph[path[i]][path[i + 1]]
                duration = edge_data.get("weight", edge_data.get("duration_minutes", 0))
                line = edge_data.get("line", "Unknown")

                next_name = graph.nodes[path[i + 1]].get("name", path[i + 1])
                print(f"   ↓ {line} line ({duration} min) to {next_name}")

                total_time += duration

        print(f"\n{'=' * 60}")
        print(f"Total journey time: {total_time} minutes")
        print(f"Number of stations: {len(path)}")
        print(f"Number of stops: {len(path) - 1}")

    except nx.NetworkXNoPath:
        print(f"❌ No path found between {from_name} and {to_name}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
