#!/usr/bin/env python3
"""
ABOUTME: Utility functions for route formatting and journey display
ABOUTME: Handles path extraction, journey leg grouping, and terminal output formatting
"""

from typing import Any, Dict, List, Tuple

import networkx as nx

from routing_config import SHOW_WAIT_TIMES, USE_EMOJI_OUTPUT, format_duration, get_transport_emoji


def extract_path_segments(graph: nx.Graph, path: list[str]) -> list[tuple[str, str, dict]]:
    """
    Extract edge data for each segment in a path.

    Args:
        graph: NetworkX graph with edge data
        path: List of node IDs forming the path

    Returns:
        List of (from_node, to_node, edge_data) tuples
    """
    segments = []

    for i in range(len(path) - 1):
        from_node = path[i]
        to_node = path[i + 1]
        edge_data = graph[from_node][to_node].copy()
        segments.append((from_node, to_node, edge_data))

    return segments


def group_journey_legs(segments: list[tuple[str, str, dict]], graph: nx.Graph) -> list[dict]:
    """
    Group consecutive segments by transport mode and line.

    Args:
        segments: List of path segments with edge data
        graph: NetworkX graph for station information

    Returns:
        List of journey legs with aggregated information
    """
    if not segments:
        return []

    legs = []
    current_leg = None

    for from_node, to_node, edge_data in segments:
        mode = edge_data.get("transport_mode", "unknown")
        line = edge_data.get("line")
        duration = edge_data.get("adjusted_duration_minutes", edge_data.get("duration_minutes", 0))

        # Check if we need to start a new leg
        start_new_leg = (
            current_leg is None
            or current_leg["mode"] != mode
            or (mode == "tube" and current_leg.get("line") != line)
        )

        if start_new_leg:
            # Save previous leg if exists
            if current_leg:
                legs.append(current_leg)

            # Start new leg
            from_station_data = graph.nodes.get(from_node, {})
            current_leg = {
                "mode": mode,
                "line": line,
                "from_station_id": from_node,
                "from_station_name": from_station_data.get("name", from_node),
                "from_coords": (from_station_data.get("lon"), from_station_data.get("lat")),
                "to_station_id": to_node,
                "to_station_name": graph.nodes[to_node].get("name", to_node),
                "to_coords": (graph.nodes[to_node].get("lon"), graph.nodes[to_node].get("lat")),
                "duration_minutes": duration,
                "base_duration_minutes": edge_data.get("base_duration_minutes", duration),
                "distance_km": edge_data.get("distance_km"),
                "stations": [from_node, to_node],
                "station_count": 1,
                "buffers": edge_data.get("buffers", []),
            }
        else:
            # Continue current leg
            current_leg["to_station_id"] = to_node
            current_leg["to_station_name"] = graph.nodes[to_node].get("name", to_node)
            current_leg["to_coords"] = (
                graph.nodes[to_node].get("lon"),
                graph.nodes[to_node].get("lat"),
            )
            current_leg["duration_minutes"] += duration
            current_leg["base_duration_minutes"] += edge_data.get("base_duration_minutes", duration)
            current_leg["stations"].append(to_node)
            current_leg["station_count"] += 1

            # Accumulate distance for bike legs
            if mode == "bike" and edge_data.get("distance_km"):
                current_leg["distance_km"] = (
                    current_leg.get("distance_km", 0) + edge_data["distance_km"]
                )

    # Don't forget the last leg
    if current_leg:
        legs.append(current_leg)

    return legs


def format_journey_summary(
    legs: list[dict],
    total_duration: float,
    start_name: str = "Your location",
    end_name: str = "Your destination",
) -> str:
    """
    Format journey summary for terminal display.

    Args:
        legs: List of journey legs from group_journey_legs
        total_duration: Total journey time in minutes
        start_name: Name for start location
        end_name: Name for end location

    Returns:
        Formatted string for terminal output
    """
    lines = []

    # Header
    lines.append("\nJourney Summary:")
    lines.append("=" * 50)
    lines.append(f"{get_transport_emoji('total')} Total time: {format_duration(total_duration)}")

    # Route overview
    route_parts = [start_name]
    for leg in legs:
        if leg["mode"] == "tube":
            route_parts.append(leg["from_station_name"])
            if leg != legs[-1] or legs[-1]["mode"] != "bike":
                route_parts.append(leg["to_station_name"])
        elif leg["mode"] == "bike" and leg == legs[-1]:
            route_parts.append(leg["from_station_name"])
    route_parts.append(end_name)

    # Remove duplicates while preserving order
    seen = set()
    unique_parts = []
    for part in route_parts:
        if part not in seen:
            seen.add(part)
            unique_parts.append(part)

    lines.append(f"Route: {' → '.join(unique_parts)}")

    return "\n".join(lines)


def format_detailed_journey(
    legs: list[dict],
    total_duration: float,
    start_name: str = "Your location",
    end_name: str = "Your destination",
    show_buffers: bool = True,
) -> str:
    """
    Format detailed journey breakdown for terminal display.

    Args:
        legs: List of journey legs from group_journey_legs
        total_duration: Total journey time in minutes
        start_name: Name for start location
        end_name: Name for end location
        show_buffers: Whether to show buffer times

    Returns:
        Formatted string for terminal output
    """
    lines = []

    # Header
    lines.append("\nDetailed Journey:")
    lines.append("=" * 50)

    leg_number = 1

    for i, leg in enumerate(legs):
        mode = leg["mode"]
        emoji = get_transport_emoji(mode)

        # Format leg based on type
        if mode == "bike":
            # Determine start and end names
            from_name = start_name if i == 0 else leg["from_station_name"]
            to_name = end_name if i == len(legs) - 1 else leg["to_station_name"]

            lines.append(
                f"\n{leg_number}. {emoji} Bike: {format_duration(leg['base_duration_minutes'])}"
            )
            lines.append(f"   From: {from_name}")
            lines.append(f"   To: {to_name}")

            if leg.get("distance_km"):
                lines.append(f"   Distance: {leg['distance_km']:.1f} km")

        elif mode == "tube":
            lines.append(
                f"\n{leg_number}. {emoji} Tube: {format_duration(leg['base_duration_minutes'])}"
            )
            if leg.get("line") and leg["line"] != "unknown":
                lines.append(f"   Line: {leg['line'].title()}")
            lines.append(f"   From: {leg['from_station_name']}")
            lines.append(f"   To: {leg['to_station_name']}")

            if leg["station_count"] > 1:
                lines.append(f"   Stops: {leg['station_count']} stations")

        # Show buffers if applicable
        if show_buffers and SHOW_WAIT_TIMES and leg.get("buffers"):
            for buffer_name, buffer_time in leg["buffers"]:
                lines.append(
                    f"\n   {get_transport_emoji('wait')} {buffer_name}: {format_duration(buffer_time)}"
                )
                leg_number += 1

        leg_number += 1

    # Total time
    lines.append(
        f"\n{get_transport_emoji('total')} Total journey time: {format_duration(total_duration)}"
    )

    return "\n".join(lines)


def format_simple_journey(legs: list[dict], total_duration: float) -> str:
    """
    Format simple one-line journey summary.

    Args:
        legs: List of journey legs
        total_duration: Total journey time

    Returns:
        One-line journey summary
    """
    parts = []

    for leg in legs:
        mode = leg["mode"]
        duration = leg["base_duration_minutes"]

        if mode == "bike":
            parts.append(f"{get_transport_emoji('bike')}{duration:.1f}min")
        elif mode == "tube":
            line = leg.get("line", "").title() if leg.get("line") else "Tube"
            parts.append(f"{get_transport_emoji('tube')}{duration:.0f}min ({line})")

    journey_str = " → ".join(parts)
    return f"{journey_str} = {format_duration(total_duration)} total"


def calculate_total_duration(segments: list[tuple[str, str, dict]]) -> float:
    """
    Calculate total duration from path segments.

    Args:
        segments: List of path segments with edge data

    Returns:
        Total duration in minutes
    """
    total = 0.0

    for _, _, edge_data in segments:
        # Use adjusted duration if available, otherwise base duration
        duration = edge_data.get("adjusted_duration_minutes", edge_data.get("duration_minutes", 0))
        total += duration

    return total


def get_line_for_tube_segment(graph: nx.Graph, from_station: str, to_station: str) -> str:
    """
    Determine which tube line connects two stations.

    Args:
        graph: NetworkX graph with station data
        from_station: Station ID
        to_station: Station ID

    Returns:
        Line name or 'unknown'
    """
    # Get lines serving both stations
    from_lines = set(graph.nodes[from_station].get("lines", []))
    to_lines = set(graph.nodes[to_station].get("lines", []))

    # Find common lines
    common_lines = from_lines.intersection(to_lines)

    if common_lines:
        # Return first common line (could be improved with line preference logic)
        return next(iter(common_lines))

    return "unknown"
