# ABOUTME: Fetches all TfL tube and train station data including coordinates, connections, and travel times
# ABOUTME: Outputs structured JSON data for the Brompton bike routing service

import json
import time
from collections import defaultdict
from datetime import datetime

import requests


class TfLStationFetcher:
    def __init__(self, app_id: str | None = None, app_key: str | None = None):
        self.base_url = "https://api.tfl.gov.uk"
        self.app_id = app_id
        self.app_key = app_key
        self.session = requests.Session()

    def _make_request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make authenticated request to TfL API with rate limiting"""
        url = f"{self.base_url}{endpoint}"

        if params is None:
            params = {}

        if self.app_id and self.app_key:
            params.update({"app_id": self.app_id, "app_key": self.app_key})

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            time.sleep(0.1)  # Rate limiting
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return {}

    def get_all_tube_lines(self) -> list[dict]:
        """Get all tube lines"""
        print("Fetching all tube lines...")
        data = self._make_request("/line/mode/tube")
        lines = []
        for line in data:
            lines.append({"id": line["id"], "name": line["name"], "modeName": line["modeName"]})
        print(f"Found {len(lines)} tube lines")
        return lines

    def get_stations_for_line(self, line_id: str) -> list[dict]:
        """Get all stations for a specific line"""
        print(f"Fetching stations for line: {line_id}")
        data = self._make_request(f"/line/{line_id}/stoppoints")

        stations = []
        for station in data:
            # Filter to only include actual stations (not bus stops, etc.)
            if "Underground" in station.get("modes", []) or "tube" in station.get("modes", []):
                stations.append(
                    {
                        "id": station["id"],
                        "naptanId": station.get("naptanId"),
                        "name": station["commonName"],
                        "lat": station["lat"],
                        "lon": station["lon"],
                        "zone": station.get("additionalProperties", [{}])[0].get("value")
                        if station.get("additionalProperties")
                        else None,
                        "modes": station.get("modes", []),
                        "lines": [line_id],  # Will aggregate this later
                    }
                )

        print(f"Found {len(stations)} stations for {line_id}")
        return stations

    def get_line_route_sequence(self, line_id: str) -> dict:
        """Get the route sequence for a line to understand station connections"""
        print(f"Fetching route sequence for line: {line_id}")
        data = self._make_request(f"/line/{line_id}/route/sequence/all")

        connections = {}
        if "stopPointSequences" in data:
            for sequence in data["stopPointSequences"]:
                direction = sequence.get("direction", "unknown")
                stops = sequence.get("stopPoint", [])

                # Create connections between adjacent stations
                for i in range(len(stops) - 1):
                    current_station = stops[i]["id"]
                    next_station = stops[i + 1]["id"]

                    if current_station not in connections:
                        connections[current_station] = []

                    connections[current_station].append(
                        {"to_station": next_station, "line": line_id, "direction": direction}
                    )

        return connections

    def get_journey_time(self, from_station: str, to_station: str) -> int:
        """Get estimated journey time between two stations in minutes"""
        # Use TfL journey planner API to get travel time
        params = {"from": from_station, "to": to_station, "mode": "tube"}

        data = self._make_request("/journey/journeyresults", params)

        if "journeys" in data and len(data["journeys"]) > 0:
            journey = data["journeys"][0]
            duration_minutes = journey.get("duration", 0)
            return duration_minutes

        return 0  # Default if no journey found

    def aggregate_station_data(self, all_stations: list[dict], all_connections: dict) -> dict:
        """Aggregate station data by removing duplicates and combining line information"""
        station_map = {}

        # Group stations by ID and aggregate lines
        for station in all_stations:
            station_id = station["id"]
            if station_id in station_map:
                # Add line to existing station
                existing_lines = set(station_map[station_id]["lines"])
                new_lines = set(station["lines"])
                station_map[station_id]["lines"] = list(existing_lines.union(new_lines))
            else:
                station_map[station_id] = station.copy()

        # Add connection information
        for station_id in station_map:
            connections = all_connections.get(station_id, [])
            station_map[station_id]["connections"] = connections
            station_map[station_id]["connection_count"] = len(connections)

        return station_map

    def fetch_all_station_data(self) -> dict:
        """Main method to fetch all station data"""
        print("Starting TfL station data fetch...")

        # Get all tube lines
        lines = self.get_all_tube_lines()

        all_stations = []
        all_connections = {}

        # For each line, get stations and connections
        for line in lines:
            line_id = line["id"]

            # Get stations for this line
            line_stations = self.get_stations_for_line(line_id)
            all_stations.extend(line_stations)

            # Get connections for this line
            line_connections = self.get_line_route_sequence(line_id)

            # Merge connections
            for station_id, connections in line_connections.items():
                if station_id not in all_connections:
                    all_connections[station_id] = []
                all_connections[station_id].extend(connections)

        # Aggregate and deduplicate station data
        station_data = self.aggregate_station_data(all_stations, all_connections)

        # Create final data structure
        result = {
            "metadata": {
                "fetch_timestamp": datetime.now().isoformat(),
                "total_stations": len(station_data),
                "total_lines": len(lines),
                "api_version": "TfL Unified API",
            },
            "lines": {line["id"]: line for line in lines},
            "stations": station_data,
        }

        return result

    def print_summary_stats(self, data: dict):
        """Print summary statistics of the fetched data"""
        stations = data["stations"]
        lines = data["lines"]

        print("\n" + "=" * 50)
        print("TFL STATION DATA SUMMARY")
        print("=" * 50)

        print(f"Total stations: {len(stations)}")
        print(f"Total lines: {len(lines)}")

        # Count stations by zone
        zone_counts = defaultdict(int)
        for station in stations.values():
            zone = station.get("zone", "Unknown")
            zone_counts[zone] += 1

        print("\nStations by zone:")
        for zone in sorted(zone_counts.keys()):
            print(f"  Zone {zone}: {zone_counts[zone]} stations")

        # Connection statistics
        connection_counts = [station["connection_count"] for station in stations.values()]
        avg_connections = sum(connection_counts) / len(connection_counts)
        max_connections = max(connection_counts)
        min_connections = min(connection_counts)

        print("\nConnection statistics:")
        print(f"  Average connections per station: {avg_connections:.1f}")
        print(f"  Maximum connections: {max_connections}")
        print(f"  Minimum connections: {min_connections}")

        # Find stations with most connections
        most_connected = sorted(
            stations.items(), key=lambda x: x[1]["connection_count"], reverse=True
        )[:5]

        print("\nMost connected stations:")
        for _station_id, station in most_connected:
            print(f"  {station['name']}: {station['connection_count']} connections")

        # Check specific stations mentioned in requirements
        baker_street_found = False
        for station in stations.values():
            if "Baker Street" in station["name"]:
                baker_street_found = True
                print("\nBaker Street details:")
                print(f"  Name: {station['name']}")
                print(f"  Lines: {station['lines']}")
                print(f"  Connections: {station['connection_count']}")
                break

        if not baker_street_found:
            print("\nWarning: Baker Street station not found!")


def main():
    """Main execution function"""
    # Initialize fetcher (no API key for now, using public endpoints)
    fetcher = TfLStationFetcher()

    # Fetch all data
    station_data = fetcher.fetch_all_station_data()

    # Save to JSON
    output_file = "tfl_stations.json"
    with open(output_file, "w") as f:
        json.dump(station_data, f, indent=2, ensure_ascii=False)

    print(f"\nData saved to {output_file}")

    # Print summary statistics
    fetcher.print_summary_stats(station_data)

    return station_data


if __name__ == "__main__":
    main()
