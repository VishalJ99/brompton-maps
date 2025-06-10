#!/usr/bin/env python3
"""
ABOUTME: Flask API server for Brompton Maps routing backend
ABOUTME: Provides REST endpoints for station data and route calculations
"""

import json
import os
import pickle
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import googlemaps
import networkx as nx
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS


# Basic imports complete


# Add src to Python path so modules can import each other
sys.path.insert(0, "src")
try:
    from route_planner_multilayer import MultiLayerBikeTransitRouter
except Exception as e:
    print(f"Failed to import MultiLayerBikeTransitRouter: {e}")
    import traceback

    traceback.print_exc()
    exit(1)

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend development

# === MODULE LEVEL INITIALIZATION (runs when gunicorn imports) ===

# Detect Railway environment
is_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT_NAME"))

# Load environment variables for local development
if not is_railway:
    load_dotenv()

# Generate frontend config.js from template
config_js_path = Path("frontend/js/config.js")
config_template_path = Path("frontend/js/config.js.template")

# Always regenerate on Railway (ephemeral filesystem)
if is_railway or not config_js_path.exists():
    if config_template_path.exists():
        # Read template
        with open(config_template_path) as template:
            template_content = template.read()

        # Get environment variables
        mapbox_token = os.environ.get("MAPBOX_ACCESS_TOKEN", "")
        google_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")

        # Replace variables
        config_content = template_content
        config_content = config_content.replace("${MAPBOX_ACCESS_TOKEN}", mapbox_token)
        config_content = config_content.replace("${GOOGLE_MAPS_API_KEY}", google_key)

        # Write config.js
        config_js_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_js_path, "w") as config:
            config.write(config_content)


# Global graph storage (declare before initialization)
tfl_graph = None
merged_graph = None
stations_data = None
multilayer_router = None  # Multi-layer router instance

# Google Maps client
gmaps_client = None

# Configuration
USE_MERGED_GRAPH = False  # Switch to True when bike graph is ready
GRAPH_FILES = {
    "tfl": "data/tfl_graph.pickle",
    "merged": "data/merged_graph.pickle",
}
MULTILAYER_GRAPH_FILE = "data/merged_multilayer_graph.pickle"

# Google Maps API key - should match frontend config
GOOGLE_MAPS_API_KEY = None  # Will be set from environment or config

# Lazy loading flag
_initialized = False


def initialize_google_maps():
    """Initialize Google Maps client if API key is available."""
    global gmaps_client, GOOGLE_MAPS_API_KEY

    # Try to get API key from environment variable first
    import os

    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

    if GOOGLE_MAPS_API_KEY:
        try:
            gmaps_client = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
            pass  # Google Maps client initialized
        except Exception as e:
            print(f"Warning: Failed to initialize Google Maps client: {e}")
            gmaps_client = None
    else:
        pass  # Google Maps API key not configured


def get_transit_duration(start_coords: tuple, end_coords: tuple) -> dict:
    """Get transit duration from Google Directions API."""
    if not gmaps_client:
        return None

    try:
        # Get transit directions
        directions_result = gmaps_client.directions(
            origin=start_coords,
            destination=end_coords,
            mode="transit",
            departure_time=datetime.now(),
            alternatives=True,  # Get multiple route options
        )

        if not directions_result:
            return None

        # Find the fastest route
        fastest_route = min(directions_result, key=lambda r: r["legs"][0]["duration"]["value"])

        duration_seconds = fastest_route["legs"][0]["duration"]["value"]
        duration_text = fastest_route["legs"][0]["duration"]["text"]

        return {"duration_minutes": round(duration_seconds / 60), "duration_text": duration_text}

    except Exception:
        return None


def load_graphs():
    """Load NetworkX graphs and station data."""
    global tfl_graph, merged_graph, stations_data, multilayer_router

    # Load TfL graph
    tfl_path = Path(GRAPH_FILES["tfl"])
    if tfl_path.exists():
        with open(tfl_path, "rb") as f:
            tfl_graph = pickle.load(f)
        pass  # TfL graph loaded
    else:
        print(f"Warning: TfL graph not found at {tfl_path}")

    # Load merged graph if available
    merged_path = Path(GRAPH_FILES["merged"])
    if merged_path.exists():
        with open(merged_path, "rb") as f:
            merged_graph = pickle.load(f)
        pass  # Merged graph loaded

    # Load station data
    stations_path = Path("data/tfl_stations.json")
    if stations_path.exists():
        with open(stations_path) as f:
            data = json.load(f)
            # Extract stations from the nested structure
            stations_data = data.get("stations", [])
        pass  # Stations loaded

    # Initialize multi-layer router
    multilayer_path = Path(MULTILAYER_GRAPH_FILE)
    if multilayer_path.exists():
        try:
            multilayer_router = MultiLayerBikeTransitRouter(graph_file=MULTILAYER_GRAPH_FILE)
            pass  # Multi-layer router initialized
        except Exception as e:
            print(f"Warning: Failed to initialize multi-layer router: {e}")
    else:
        pass  # Multi-layer graph not available


def ensure_initialized():
    """Ensure graphs and services are loaded before first use."""
    global _initialized
    if not _initialized:
        pass  # Initializing services on first request
        initialize_google_maps()
        load_graphs()
        _initialized = True
        pass  # Initialization complete


def get_active_graph():
    """Get the currently active graph based on configuration."""
    if USE_MERGED_GRAPH and merged_graph is not None:
        return merged_graph
    return tfl_graph


@app.route("/api/stations", methods=["GET"])
def get_stations():
    """Get all stations with their metadata."""
    ensure_initialized()

    if stations_data is None:
        return jsonify({"error": "Station data not loaded"}), 500

    # Format stations for frontend
    stations = []
    # stations_data is a dict with station IDs as keys
    for _station_id, station in stations_data.items():
        stations.append(
            {
                "id": station["id"],
                "name": station["name"],
                "lat": station["lat"],
                "lon": station["lon"],
                "lines": station["lines"],
                "zone": station.get("zone", None),
            }
        )

    return jsonify({"stations": stations})


@app.route("/api/route/point-to-point", methods=["POST"])
def route_point_to_point():
    """Calculate route between two arbitrary points (future bike+tube support)."""
    return jsonify({"error": "Point-to-point routing not yet implemented"}), 501


@app.route("/api/route/coordinates", methods=["POST"])
def route_coordinates():
    """Calculate multi-modal route between two coordinates using multi-layer routing."""
    ensure_initialized()

    if not multilayer_router:
        return jsonify({"error": "Multi-layer router not initialized"}), 503

    # Get coordinates from request
    data = request.json
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    start_lon = data.get("start_lon")
    start_lat = data.get("start_lat")
    end_lon = data.get("end_lon")
    end_lat = data.get("end_lat")

    # Validate inputs
    if any(coord is None for coord in [start_lon, start_lat, end_lon, end_lat]):
        return jsonify({"error": "Missing coordinates"}), 400

    try:
        start_coords = (float(start_lon), float(start_lat))
        end_coords = (float(end_lon), float(end_lat))
    except ValueError:
        return jsonify({"error": "Invalid coordinate format"}), 400

    # Optional parameters
    station_access_time = data.get("station_access_time", 2.0)
    train_waiting_time = data.get("train_waiting_time", 5.0)
    line_change_time = data.get("line_change_time", 5.0)

    try:
        # Update router with custom timing parameters
        multilayer_router.station_access_time = station_access_time
        multilayer_router.train_waiting_time = train_waiting_time
        multilayer_router.line_change_time = line_change_time

        # Find optimal route (always compares direct bike vs multi-modal)
        route_info = multilayer_router.find_optimal_route(start_coords, end_coords)

        if not route_info:
            return jsonify({"error": "No route found"}), 404

        # Get transit comparison - Google Maps expects (lat, lon) but we have (lon, lat)
        transit_comparison = get_transit_duration(
            (start_coords[1], start_coords[0]),  # Swap to (lat, lon)
            (end_coords[1], end_coords[0]),  # Swap to (lat, lon)
        )

        # Format response for frontend
        response = {
            "status": "success",
            "route": {
                "segments": [],
                "total_duration": route_info["total_duration"],
                "is_direct_bike": route_info.get("is_direct_bike", False),
                "transit_comparison": transit_comparison,  # Will be None if API fails
            },
        }

        # Process segments for frontend consumption
        for _i, segment in enumerate(route_info["segments"]):
            formatted_segment = {
                "type": segment["transport_mode"],
                "from_name": segment["from_name"],
                "to_name": segment["to_name"],
                "duration_minutes": segment["duration_minutes"],
            }

            if segment["transport_mode"] == "bike":
                # Add bike-specific data
                formatted_segment["distance_km"] = segment.get("distance_km", 0)
                formatted_segment["original_duration_minutes"] = segment.get(
                    "original_duration_minutes", segment["duration_minutes"]
                )
                formatted_segment["station_access_buffer_minutes"] = segment.get(
                    "station_access_buffer_minutes", 0
                )

                # Get bike route geometry from Google Maps
                if segment["from_node"] == "start":
                    bike_from = start_coords
                else:
                    # Extract station coordinates from graph
                    node_data = multilayer_router.graph.nodes[segment["from_node"]]
                    bike_from = (node_data["lon"], node_data["lat"])

                if segment["to_node"] == "end":
                    bike_to = end_coords
                else:
                    # Extract station coordinates from graph
                    node_data = multilayer_router.graph.nodes[segment["to_node"]]
                    bike_to = (node_data["lon"], node_data["lat"])

                # Get route with geometry
                bike_result = multilayer_router.bike_router.get_route(bike_from, bike_to)
                if bike_result.success:
                    if bike_result.geometry:
                        formatted_segment["geometry"] = bike_result.geometry
                    else:
                        # Fallback to straight line
                        formatted_segment["geometry"] = [list(bike_from), list(bike_to)]
                else:
                    # Fallback to straight line
                    formatted_segment["geometry"] = [list(bike_from), list(bike_to)]

            elif segment["transport_mode"] == "tube":
                # Add tube-specific data
                formatted_segment["line"] = segment.get(
                    "tube_line", segment.get("from_line", "unknown")
                )
                formatted_segment["from_station"] = segment["from_station"]
                formatted_segment["to_station"] = segment["to_station"]

                # Check if this is a line change
                if segment.get("edge_type") == "line_change":
                    formatted_segment["type"] = "line_change"
                    formatted_segment["from_line"] = segment["from_line"]
                    formatted_segment["to_line"] = segment["to_line"]

            response["route"]["segments"].append(formatted_segment)

        return jsonify(response)

    except Exception:
        # Log error for debugging but don't expose internals
        import traceback

        traceback.print_exc()
        return jsonify({"error": "Route calculation failed"}), 500


@app.route("/api/graph/status", methods=["GET"])
def graph_status():
    """Get status of loaded graphs."""
    ensure_initialized()

    status = {
        "tfl_graph_loaded": tfl_graph is not None,
        "merged_graph_loaded": merged_graph is not None,
        "multilayer_router_loaded": multilayer_router is not None,
        "active_graph": "merged" if USE_MERGED_GRAPH and merged_graph else "tfl",
        "tfl_stats": None,
        "merged_stats": None,
        "multilayer_stats": None,
    }

    if tfl_graph:
        status["tfl_stats"] = {
            "nodes": tfl_graph.number_of_nodes(),
            "edges": tfl_graph.number_of_edges(),
        }

    if merged_graph:
        status["merged_stats"] = {
            "nodes": merged_graph.number_of_nodes(),
            "edges": merged_graph.number_of_edges(),
        }

    if multilayer_router:
        status["multilayer_stats"] = {
            "nodes": multilayer_router.graph.number_of_nodes(),
            "edges": multilayer_router.graph.number_of_edges(),
        }

    return jsonify(status)


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    pass  # Health check
    return jsonify({"status": "ok", "graphs_loaded": tfl_graph is not None})


# Frontend serving routes
@app.route("/")
def serve_index():
    """Serve the frontend index.html"""
    pass  # Serving index
    return send_from_directory("frontend", "index.html")


@app.route("/js/<path:filename>")
def serve_js(filename):
    """Serve JavaScript files"""
    return send_from_directory("frontend/js", filename)


@app.route("/css/<path:filename>")
def serve_css(filename):
    """Serve CSS files"""
    return send_from_directory("frontend/css", filename)


# === MODULE LEVEL INITIALIZATION COMPLETION ===
# Using lazy loading - graphs will be loaded on first API request


if __name__ == "__main__":
    # This block only runs when you execute 'python app.py' directly
    # It does NOT run when gunicorn imports the module
    print("=== RUNNING IN DEVELOPMENT MODE ===")

    # Run Flask development server
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask development server on http://0.0.0.0:{port}")
    print("Warning: Use gunicorn for production deployments")
    app.run(debug=False, host="0.0.0.0", port=port)
