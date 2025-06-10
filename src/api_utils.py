#!/usr/bin/env python3
"""
ABOUTME: Utility functions for API server operations
ABOUTME: Handles graph operations, route formatting, and tube line styling
"""

from typing import Dict, List, Optional, Tuple


# TfL line colors (official branding colors)
TUBE_LINE_COLORS = {
    "bakerloo": "#B36305",
    "central": "#E32017",
    "circle": "#FFD300",
    "district": "#00782A",
    "hammersmith-city": "#F3A9BB",
    "jubilee": "#A0A5A9",
    "metropolitan": "#9B0056",
    "northern": "#000000",
    "piccadilly": "#003688",
    "victoria": "#0098D4",
    "waterloo-city": "#95CDBA",
}

# Default color for unknown lines
DEFAULT_LINE_COLOR = "#666666"


def get_line_color(line_name: str) -> str:
    """
    Get the official color for a tube line.

    Args:
        line_name: Name of the tube line

    Returns:
        Hex color code for the line
    """
    # Normalize line name (lowercase, remove 'line' suffix)
    normalized = line_name.lower().replace(" line", "").strip()

    # Handle special cases
    if normalized == "hammersmith & city":
        normalized = "hammersmith-city"
    elif normalized == "waterloo & city":
        normalized = "waterloo-city"

    return TUBE_LINE_COLORS.get(normalized, DEFAULT_LINE_COLOR)


def format_duration(minutes: float) -> str:
    """
    Format duration in minutes to human-readable string.

    Args:
        minutes: Duration in minutes

    Returns:
        Formatted string (e.g., "5 min", "1h 15m")
    """
    if minutes < 1:
        return "< 1 min"
    elif minutes < 60:
        return f"{int(minutes)} min"
    else:
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        if mins == 0:
            return f"{hours}h"
        return f"{hours}h {mins}m"


def extract_line_from_path(graph, from_id: str, to_id: str) -> str:
    """
    Extract the tube line connecting two stations.

    Args:
        graph: NetworkX graph
        from_id: From station ID
        to_id: To station ID

    Returns:
        Line name or "Unknown"
    """
    if graph.has_edge(from_id, to_id):
        edge_data = graph[from_id][to_id]
        # Try different possible attribute names
        return edge_data.get("line", edge_data.get("lines", "Unknown"))

    # If no direct edge, check which lines serve both stations
    from_lines = set(graph.nodes[from_id].get("lines", []))
    to_lines = set(graph.nodes[to_id].get("lines", []))
    common_lines = from_lines.intersection(to_lines)

    if common_lines:
        # Return the first common line
        return next(iter(common_lines))

    return "Unknown"


def group_segments_by_line(segments: list[dict]) -> list[dict]:
    """
    Group consecutive segments that use the same tube line.

    Args:
        segments: List of journey segments

    Returns:
        List of grouped journey legs
    """
    if not segments:
        return []

    legs = []
    current_leg = None

    for segment in segments:
        line = segment.get("line", "Unknown")

        if current_leg is None or current_leg["line"] != line:
            # Start new leg
            if current_leg:
                legs.append(current_leg)

            current_leg = {
                "mode": "tube",
                "line": line,
                "color": get_line_color(line),
                "from_id": segment["from_id"],
                "from_name": segment["from_name"],
                "to_id": segment["to_id"],
                "to_name": segment["to_name"],
                "duration_minutes": segment["duration_minutes"],
                "segments": [segment],
            }
        else:
            # Continue current leg
            current_leg["to_id"] = segment["to_id"]
            current_leg["to_name"] = segment["to_name"]
            current_leg["duration_minutes"] += segment["duration_minutes"]
            current_leg["segments"].append(segment)

    if current_leg:
        legs.append(current_leg)

    return legs


def calculate_line_changes(journey_legs: list[dict]) -> int:
    """
    Calculate the number of line changes in a journey.

    Args:
        journey_legs: List of journey legs

    Returns:
        Number of line changes
    """
    if len(journey_legs) <= 1:
        return 0

    changes = 0
    for i in range(1, len(journey_legs)):
        if journey_legs[i]["line"] != journey_legs[i - 1]["line"]:
            changes += 1

    return changes


def add_transfer_buffers(journey_legs: list[dict], buffer_minutes: float = 5.0) -> float:
    """
    Add transfer time buffers to journey legs.

    Args:
        journey_legs: List of journey legs
        buffer_minutes: Time to add for each line change

    Returns:
        Total buffer time added
    """
    changes = calculate_line_changes(journey_legs)
    return changes * buffer_minutes


def format_station_name(name: str) -> str:
    """
    Format station name for display.

    Args:
        name: Raw station name

    Returns:
        Formatted station name
    """
    # Remove "Underground Station" suffix
    formatted = name.replace(" Underground Station", "")

    # Fix common formatting issues
    replacements = {
        " And ": " & ",
        "Kings Cross": "King's Cross",
        "Queens Park": "Queen's Park",
        "St Johns Wood": "St John's Wood",
        "St Pauls": "St Paul's",
        "Regents Park": "Regent's Park",
        "Earls Court": "Earl's Court",
    }

    for old, new in replacements.items():
        formatted = formatted.replace(old, new)

    return formatted


def create_geojson_line(coords: list[tuple[float, float]], properties: dict | None = None) -> dict:
    """
    Create a GeoJSON LineString feature.

    Args:
        coords: List of (lon, lat) tuples
        properties: Optional properties for the feature

    Returns:
        GeoJSON feature dict
    """
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": properties or {},
    }


def create_station_marker(station: dict) -> dict:
    """
    Create a marker object for a station.

    Args:
        station: Station data with id, name, lat, lon, lines

    Returns:
        Marker object for frontend
    """
    # Get primary line color (first line)
    primary_line = station.get("lines", ["unknown"])[0]
    color = get_line_color(primary_line)

    return {
        "id": station["id"],
        "name": format_station_name(station["name"]),
        "coordinates": [station["lon"], station["lat"]],
        "lines": station.get("lines", []),
        "color": color,
        "zone": station.get("zone"),
    }


def validate_coordinates(lat: float, lon: float) -> bool:
    """
    Validate that coordinates are within reasonable London bounds.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        True if coordinates are valid
    """
    # Rough bounds for Greater London
    MIN_LAT, MAX_LAT = 51.2, 51.7
    MIN_LON, MAX_LON = -0.6, 0.3

    return MIN_LAT <= lat <= MAX_LAT and MIN_LON <= lon <= MAX_LON
