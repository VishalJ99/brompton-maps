#!/usr/bin/env python3
"""
ABOUTME: Pluggable bike routing API architecture for easy provider switching
ABOUTME: Supports OSRM, GraphHopper, Google Maps and other providers via common interface
"""

import json
import os
from abc import ABC, abstractmethod
from typing import NamedTuple, Optional

import requests
from dotenv import load_dotenv


# Load environment variables
load_dotenv()


def decode_polyline(polyline: str) -> list[list[float]]:
    """
    Decode Google Maps polyline to list of [longitude, latitude] coordinates.

    Args:
        polyline: Encoded polyline string from Google Maps

    Returns:
        List of [longitude, latitude] coordinate pairs
    """
    coordinates = []
    index = 0
    lat = 0
    lng = 0

    while index < len(polyline):
        # Decode latitude
        shift = 0
        result = 0
        while True:
            byte = ord(polyline[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        lat += ~(result >> 1) if result & 1 else result >> 1

        # Decode longitude
        shift = 0
        result = 0
        while True:
            byte = ord(polyline[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        lng += ~(result >> 1) if result & 1 else result >> 1

        # Convert to decimal degrees and append as [lon, lat]
        coordinates.append([lng / 1e5, lat / 1e5])

    return coordinates


class BikeRouteResult(NamedTuple):
    """Result of a bike routing query."""

    duration_minutes: float
    distance_km: float
    success: bool
    error_message: str | None = None
    provider: str | None = None
    geometry: list[list[float]] | None = None  # Route geometry as [[lon, lat], ...]


class BikeRoutingProvider(ABC):
    """Abstract base class for bike routing providers."""

    @abstractmethod
    def get_route(
        self, start_coords: tuple[float, float], end_coords: tuple[float, float]
    ) -> BikeRouteResult:
        """
        Get bike route between two coordinates.

        Args:
            start_coords: (longitude, latitude) of start point
            end_coords: (longitude, latitude) of end point

        Returns:
            BikeRouteResult with duration, distance, and success status
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for identification."""
        pass


class OSRMProvider(BikeRoutingProvider):
    """OSRM bike routing provider with configurable speed scaling."""

    def __init__(self, target_speed_kmh: float = 15.0, timeout: int = 10):
        """
        Initialize OSRM provider.

        Args:
            target_speed_kmh: Target cycling speed for realistic estimates (default: 15.0)
            timeout: Request timeout in seconds (default: 10)
        """
        self.target_speed_kmh = target_speed_kmh
        self.timeout = timeout

    @property
    def name(self) -> str:
        return f"OSRM (scaled to {self.target_speed_kmh} km/h)"

    def get_route(
        self, start_coords: tuple[float, float], end_coords: tuple[float, float]
    ) -> BikeRouteResult:
        """Get bike route using OSRM API with speed scaling."""
        start_lng, start_lat = start_coords
        end_lng, end_lat = end_coords

        url = f"http://router.project-osrm.org/route/v1/cycling/{start_lng},{start_lat};{end_lng},{end_lat}"
        params = {"overview": "full", "steps": "false", "geometries": "geojson"}

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()

            if data.get("code") != "Ok":
                return BikeRouteResult(
                    0, 0, False, f"OSRM error: {data.get('message', 'Unknown error')}", self.name
                )

            routes = data.get("routes", [])
            if not routes:
                return BikeRouteResult(0, 0, False, "No routes found", self.name, None)

            route = routes[0]
            distance_meters = route.get("distance", 0)

            distance_km = distance_meters / 1000

            # Calculate realistic duration based on target speed
            realistic_duration_minutes = (distance_km / self.target_speed_kmh) * 60

            # Extract geometry if available
            geometry = None
            if "geometry" in route and "coordinates" in route["geometry"]:
                geometry = route["geometry"]["coordinates"]

            return BikeRouteResult(
                realistic_duration_minutes, distance_km, True, None, self.name, geometry
            )

        except requests.exceptions.RequestException as e:
            return BikeRouteResult(0, 0, False, f"Network error: {e!s}", self.name, None)
        except json.JSONDecodeError as e:
            return BikeRouteResult(0, 0, False, f"JSON decode error: {e!s}", self.name, None)
        except Exception as e:
            return BikeRouteResult(0, 0, False, f"Unexpected error: {e!s}", self.name, None)


class GraphHopperProvider(BikeRoutingProvider):
    """GraphHopper bike routing provider."""

    def __init__(self, api_key: str | None = None, timeout: int = 10):
        """
        Initialize GraphHopper provider.

        Args:
            api_key: GraphHopper API key (if None, will try to load from GRAPHHOPPER_API_KEY env var)
            timeout: Request timeout in seconds (default: 10)
        """
        self.api_key = api_key or os.getenv("GRAPHHOPPER_API_KEY")
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "GraphHopper"

    def get_route(
        self, start_coords: tuple[float, float], end_coords: tuple[float, float]
    ) -> BikeRouteResult:
        """Get bike route using GraphHopper API."""
        if not self.api_key:
            return BikeRouteResult(
                0,
                0,
                False,
                "No API key found. Set GRAPHHOPPER_API_KEY environment variable.",
                self.name,
            )

        start_lng, start_lat = start_coords
        end_lng, end_lat = end_coords

        url = "https://graphhopper.com/api/1/route"
        params = {
            "point": [f"{start_lat},{start_lng}", f"{end_lat},{end_lng}"],
            "vehicle": "bike",
            "locale": "en",
            "calc_points": "false",
            "debug": "false",
            "elevation": "false",
            "points_encoded": "false",
            "key": self.api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()

            if "paths" not in data or len(data["paths"]) == 0:
                return BikeRouteResult(
                    0,
                    0,
                    False,
                    f"GraphHopper error: {data.get('message', 'No paths found')}",
                    self.name,
                )

            path = data["paths"][0]
            duration_ms = path.get("time", 0)
            distance_meters = path.get("distance", 0)

            duration_minutes = duration_ms / (1000 * 60)
            distance_km = distance_meters / 1000

            return BikeRouteResult(duration_minutes, distance_km, True, None, self.name)

        except requests.exceptions.RequestException as e:
            return BikeRouteResult(0, 0, False, f"Network error: {e!s}", self.name, None)
        except json.JSONDecodeError as e:
            return BikeRouteResult(0, 0, False, f"JSON decode error: {e!s}", self.name, None)
        except Exception as e:
            return BikeRouteResult(0, 0, False, f"Unexpected error: {e!s}", self.name, None)


class GoogleMapsProvider(BikeRoutingProvider):
    """Google Maps bike routing provider (placeholder for future implementation)."""

    def __init__(self, api_key: str | None = None, timeout: int = 10):
        """
        Initialize Google Maps provider.

        Args:
            api_key: Google Maps API key (if None, will try to load from GOOGLE_MAPS_API_KEY env var)
            timeout: Request timeout in seconds (default: 10)
        """
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "Google Maps"

    def get_route(
        self, start_coords: tuple[float, float], end_coords: tuple[float, float]
    ) -> BikeRouteResult:
        """Get bike route using Google Maps Directions API."""
        if not self.api_key:
            return BikeRouteResult(
                0,
                0,
                False,
                "No API key found. Set GOOGLE_MAPS_API_KEY environment variable.",
                self.name,
            )

        start_lng, start_lat = start_coords
        end_lng, end_lat = end_coords

        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": f"{start_lat},{start_lng}",
            "destination": f"{end_lat},{end_lng}",
            "mode": "bicycling",
            "key": self.api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()

            if data.get("status") != "OK":
                return BikeRouteResult(
                    0,
                    0,
                    False,
                    f"Google Maps error: {data.get('status', 'Unknown error')}",
                    self.name,
                )

            routes = data.get("routes", [])
            if not routes:
                return BikeRouteResult(0, 0, False, "No routes found", self.name, None)

            route = routes[0]
            leg = route["legs"][0]  # Single leg for direct routing

            # Extract duration and distance
            duration_seconds = leg["duration"]["value"]
            distance_meters = leg["distance"]["value"]

            duration_minutes = duration_seconds / 60
            distance_km = distance_meters / 1000

            # Extract route geometry from overview polyline
            geometry = None
            if "overview_polyline" in route:
                polyline = route["overview_polyline"]["points"]
                # Decode polyline to coordinates
                geometry = decode_polyline(polyline)

            return BikeRouteResult(duration_minutes, distance_km, True, None, self.name, geometry)

        except requests.exceptions.RequestException as e:
            return BikeRouteResult(0, 0, False, f"Network error: {e!s}", self.name, None)
        except json.JSONDecodeError as e:
            return BikeRouteResult(0, 0, False, f"JSON decode error: {e!s}", self.name, None)
        except Exception as e:
            return BikeRouteResult(0, 0, False, f"Unexpected error: {e!s}", self.name, None)


class BikeRouter:
    """Main bike routing class that delegates to pluggable providers."""

    def __init__(self, provider: BikeRoutingProvider):
        """
        Initialize router with a specific provider.

        Args:
            provider: BikeRoutingProvider instance to use for routing
        """
        self.provider = provider

    def get_route(
        self, start_coords: tuple[float, float], end_coords: tuple[float, float]
    ) -> BikeRouteResult:
        """Get bike route using the configured provider."""
        return self.provider.get_route(start_coords, end_coords)

    def get_route_to_station(
        self, start_coords: tuple[float, float], station_coords: tuple[float, float]
    ) -> BikeRouteResult:
        """Get bike route to a station (convenience method)."""
        return self.get_route(start_coords, station_coords)

    @property
    def provider_name(self) -> str:
        """Get the name of the current provider."""
        return self.provider.name


# Convenience factory functions
def create_osrm_router(target_speed_kmh: float = 15.0) -> BikeRouter:
    """Create a bike router using OSRM with speed scaling."""
    return BikeRouter(OSRMProvider(target_speed_kmh))


def create_graphhopper_router(api_key: str | None = None) -> BikeRouter:
    """Create a bike router using GraphHopper."""
    return BikeRouter(GraphHopperProvider(api_key))


def create_google_maps_router(api_key: str | None = None) -> BikeRouter:
    """Create a bike router using Google Maps."""
    return BikeRouter(GoogleMapsProvider(api_key))


def create_default_router() -> BikeRouter:
    """Create the default bike router (OSRM with 15 km/h scaling)."""
    return create_osrm_router(15.0)
