# ABOUTME: Modular utility functions for TfL station data and journey planning
# ABOUTME: Provides station lookup, travel time queries, and bike routing functions

import json
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import requests

from bike_routing import BikeRouter, BikeRouteResult, create_default_router


@dataclass
class JourneyResult:
    """Represents a journey between two stations"""

    from_station: str
    to_station: str
    duration_minutes: int
    legs: int
    success: bool
    error_message: str | None = None


class TfLStationUtils:
    """Utility class for TfL station operations and journey planning"""

    def __init__(
        self, stations_file: str = "tfl_stations.json", bike_router: BikeRouter | None = None
    ):
        """Initialize with station data and optional bike router"""
        self.stations_data = self._load_stations_data(stations_file)
        self.base_url = "https://api.tfl.gov.uk"
        self.session = requests.Session()
        self.bike_router = bike_router or create_default_router()

    def _load_stations_data(self, stations_file: str) -> dict:
        """Load station data from JSON file"""
        try:
            with open(stations_file) as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Station data file {stations_file} not found. Run fetch_tfl_stations.py first."
            )

    def find_station_by_name(self, search_name: str) -> tuple[str | None, dict | None]:
        """
        Find station by partial name match

        Args:
            search_name: Station name to search for (case insensitive, partial match)

        Returns:
            Tuple of (station_id, station_data) or (None, None) if not found
        """
        search_name_lower = search_name.lower()
        matches = []

        for station_id, station in self.stations_data["stations"].items():
            if search_name_lower in station["name"].lower():
                matches.append((station_id, station))

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            # Multiple matches - return the most exact one
            exact_matches = [
                (sid, s) for sid, s in matches if search_name_lower == s["name"].lower()
            ]
            if exact_matches:
                return exact_matches[0]

            # If no exact match, return the shortest name (most likely match)
            matches.sort(key=lambda x: len(x[1]["name"]))
            return matches[0]

        return None, None

    def find_stations_by_name(self, search_name: str) -> list[tuple[str, dict]]:
        """
        Find all stations matching the search name

        Args:
            search_name: Station name to search for

        Returns:
            List of (station_id, station_data) tuples
        """
        search_name_lower = search_name.lower()
        matches = []

        for station_id, station in self.stations_data["stations"].items():
            if search_name_lower in station["name"].lower():
                matches.append((station_id, station))

        return matches

    def get_station_info(self, station_id: str) -> dict | None:
        """Get detailed information about a station by ID"""
        return self.stations_data["stations"].get(station_id)

    def get_journey_time(
        self, from_station: str, to_station: str, by_name: bool = True
    ) -> JourneyResult:
        """
        Get travel time between two stations

        Args:
            from_station: Source station (name or ID depending on by_name)
            to_station: Destination station (name or ID depending on by_name)
            by_name: If True, treat inputs as station names; if False, as station IDs

        Returns:
            JourneyResult with travel time and details
        """
        # Convert names to IDs if needed
        if by_name:
            from_id, from_data = self.find_station_by_name(from_station)
            to_id, to_data = self.find_station_by_name(to_station)

            if not from_id:
                return JourneyResult(
                    from_station=from_station,
                    to_station=to_station,
                    duration_minutes=0,
                    legs=0,
                    success=False,
                    error_message=f"Source station '{from_station}' not found",
                )

            if not to_id:
                return JourneyResult(
                    from_station=from_station,
                    to_station=to_station,
                    duration_minutes=0,
                    legs=0,
                    success=False,
                    error_message=f"Destination station '{to_station}' not found",
                )
        else:
            from_id, to_id = from_station, to_station
            from_data = self.get_station_info(from_id)
            to_data = self.get_station_info(to_id)

        # Make API request for journey time
        url = f"{self.base_url}/Journey/JourneyResults/{from_id}/to/{to_id}"

        try:
            response = self.session.get(url)
            time.sleep(0.1)  # Rate limiting

            if response.status_code == 200:
                data = response.json()
                if "journeys" in data and len(data["journeys"]) > 0:
                    journey = data["journeys"][0]
                    return JourneyResult(
                        from_station=from_data["name"] if from_data else from_station,
                        to_station=to_data["name"] if to_data else to_station,
                        duration_minutes=journey.get("duration", 0),
                        legs=len(journey.get("legs", [])),
                        success=True,
                    )
                else:
                    return JourneyResult(
                        from_station=from_data["name"] if from_data else from_station,
                        to_station=to_data["name"] if to_data else to_station,
                        duration_minutes=0,
                        legs=0,
                        success=False,
                        error_message="No journey found in API response",
                    )
            else:
                return JourneyResult(
                    from_station=from_data["name"] if from_data else from_station,
                    to_station=to_data["name"] if to_data else to_station,
                    duration_minutes=0,
                    legs=0,
                    success=False,
                    error_message=f"API error: {response.status_code}",
                )

        except Exception as e:
            return JourneyResult(
                from_station=from_data["name"] if from_data else from_station,
                to_station=to_data["name"] if to_data else to_station,
                duration_minutes=0,
                legs=0,
                success=False,
                error_message=f"Request failed: {e!s}",
            )

    def get_stations_on_line(self, line_name: str) -> list[dict]:
        """Get all stations serving a specific line"""
        line_name_lower = line_name.lower()
        stations = []

        for station_id, station in self.stations_data["stations"].items():
            station_lines = [line.lower() for line in station.get("lines", [])]
            if line_name_lower in station_lines:
                stations.append(
                    {
                        "id": station_id,
                        "name": station["name"],
                        "lat": station["lat"],
                        "lon": station["lon"],
                        "lines": station["lines"],
                    }
                )

        return stations

    def get_common_lines(self, station1: str, station2: str) -> list[str]:
        """Get lines that serve both stations"""
        _, data1 = self.find_station_by_name(station1)
        _, data2 = self.find_station_by_name(station2)

        if not data1 or not data2:
            return []

        lines1 = {line.lower() for line in data1.get("lines", [])}
        lines2 = {line.lower() for line in data2.get("lines", [])}

        return list(lines1.intersection(lines2))

    def get_bike_route(
        self, start_coords: tuple[float, float], end_coords: tuple[float, float]
    ) -> BikeRouteResult:
        """
        Get bike routing information between two coordinates using the configured bike router.

        Args:
            start_coords: (longitude, latitude) of start point
            end_coords: (longitude, latitude) of end point

        Returns:
            BikeRouteResult with duration, distance, and success status
        """
        return self.bike_router.get_route(start_coords, end_coords)

    def get_bike_route_to_station(
        self, start_coords: tuple[float, float], station_name: str
    ) -> BikeRouteResult:
        """
        Get bike routing from coordinates to a station.

        Args:
            start_coords: (longitude, latitude) of start point
            station_name: Name of destination station

        Returns:
            BikeRouteResult with duration, distance, and success status
        """
        _, station_data = self.find_station_by_name(station_name)

        if not station_data:
            return BikeRouteResult(0, 0, False, f"Station '{station_name}' not found")

        station_coords = (station_data["lon"], station_data["lat"])
        return self.get_bike_route(start_coords, station_coords)

    def find_nearby_stations(
        self, coords: tuple[float, float], max_distance_km: float = 2.0
    ) -> list[dict]:
        """
        Find stations within cycling distance of given coordinates.

        Args:
            coords: (longitude, latitude) of search point
            max_distance_km: Maximum distance to search (as the crow flies)

        Returns:
            List of station data with distances, sorted by distance
        """
        import math

        lng, lat = coords
        nearby_stations = []

        for station_id, station in self.stations_data["stations"].items():
            # Calculate approximate distance using Haversine formula
            station_lat = station["lat"]
            station_lng = station["lon"]

            # Convert to radians
            lat1, lng1 = math.radians(lat), math.radians(lng)
            lat2, lng2 = math.radians(station_lat), math.radians(station_lng)

            # Haversine formula
            dlat = lat2 - lat1
            dlng = lng2 - lng1
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
            c = 2 * math.asin(math.sqrt(a))
            distance_km = 6371 * c  # Earth's radius in km

            if distance_km <= max_distance_km:
                station_copy = station.copy()
                station_copy["id"] = station_id
                station_copy["distance_km"] = round(distance_km, 2)
                nearby_stations.append(station_copy)

        # Sort by distance
        nearby_stations.sort(key=lambda x: x["distance_km"])
        return nearby_stations


# Convenience functions for direct use
def get_travel_time(from_station: str, to_station: str) -> JourneyResult:
    """
    Convenience function to get travel time between two stations by name

    Args:
        from_station: Source station name
        to_station: Destination station name

    Returns:
        JourneyResult with travel time and details
    """
    utils = TfLStationUtils()
    return utils.get_journey_time(from_station, to_station)


def find_station(station_name: str) -> dict | None:
    """
    Convenience function to find a station by name

    Args:
        station_name: Station name to search for

    Returns:
        Station data dictionary or None if not found
    """
    utils = TfLStationUtils()
    _, station_data = utils.find_station_by_name(station_name)
    return station_data


def get_bike_time(
    start_coords: tuple[float, float], end_coords: tuple[float, float]
) -> BikeRouteResult:
    """
    Convenience function to get bike routing between two coordinates

    Args:
        start_coords: (longitude, latitude) of start point
        end_coords: (longitude, latitude) of end point

    Returns:
        BikeRouteResult with duration, distance, and success status
    """
    utils = TfLStationUtils()
    return utils.get_bike_route(start_coords, end_coords)


def get_bike_time_to_station(
    start_coords: tuple[float, float], station_name: str
) -> BikeRouteResult:
    """
    Convenience function to get bike routing from coordinates to a station

    Args:
        start_coords: (longitude, latitude) of start point
        station_name: Name of destination station

    Returns:
        BikeRouteResult with duration, distance, and success status
    """
    utils = TfLStationUtils()
    return utils.get_bike_route_to_station(start_coords, station_name)


def find_nearby_stations(coords: tuple[float, float], max_distance_km: float = 2.0) -> list[dict]:
    """
    Convenience function to find stations within cycling distance

    Args:
        coords: (longitude, latitude) of search point
        max_distance_km: Maximum distance to search (default 2km)

    Returns:
        List of station data with distances, sorted by distance
    """
    utils = TfLStationUtils()
    return utils.find_nearby_stations(coords, max_distance_km)


if __name__ == "__main__":
    # Example usage and testing
    utils = TfLStationUtils()

    # Test the utility functions
    print("Testing TfL Station Utilities with Bike Routing")
    print("=" * 50)

    # Test station finding
    print("\n1. Finding stations:")
    baker_id, baker_data = utils.find_station_by_name("Baker Street")
    print(f"Baker Street: {baker_data['name'] if baker_data else 'Not found'}")

    wembley_id, wembley_data = utils.find_station_by_name("Wembley Park")
    print(f"Wembley Park: {wembley_data['name'] if wembley_data else 'Not found'}")

    # Test journey time
    print("\n2. Transit journey times:")
    result = utils.get_journey_time("Preston Road", "Wembley Park")
    if result.success:
        print(f"{result.from_station} → {result.to_station}: {result.duration_minutes} minutes")
    else:
        print(f"Journey failed: {result.error_message}")

    # Test bike routing
    print("\n3. Bike routing:")
    paddington_coords = (-0.1759, 51.5154)  # Paddington Station
    baker_coords = (-0.1574, 51.5226)  # Baker Street Station

    bike_result = utils.get_bike_route(paddington_coords, baker_coords)
    if bike_result.success:
        print(
            f"Paddington → Baker Street (bike): {bike_result.duration_minutes:.1f} minutes, {bike_result.distance_km:.2f} km"
        )
    else:
        print(f"Bike route failed: {bike_result.error_message}")

    # Test bike routing to station by name
    print("\n4. Bike routing to station:")
    hyde_park_coords = (-0.1527, 51.5028)  # Hyde Park Corner
    bike_to_station = utils.get_bike_route_to_station(hyde_park_coords, "King's Cross")
    if bike_to_station.success:
        print(
            f"Hyde Park Corner → King's Cross (bike): {bike_to_station.duration_minutes:.1f} minutes, {bike_to_station.distance_km:.2f} km"
        )
    else:
        print(f"Bike to station failed: {bike_to_station.error_message}")

    # Test finding nearby stations
    print("\n5. Nearby stations:")
    nearby = utils.find_nearby_stations(hyde_park_coords, max_distance_km=1.5)
    print("Stations within 1.5km of Hyde Park Corner:")
    for station in nearby[:5]:  # Show first 5
        print(f"  {station['name']}: {station['distance_km']}km")

    # Test common lines
    print("\n6. Common lines:")
    common = utils.get_common_lines("Preston Road", "Baker Street")
    print(f"Preston Road ↔ Baker Street: {common}")
