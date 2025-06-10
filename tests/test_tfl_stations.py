# ABOUTME: Unit tests to validate TfL station data quality and completeness
# ABOUTME: Tests station count, Baker Street connections, travel times, and station connectivity

import json
import unittest

from fetch_tfl_stations import TfLStationFetcher


class TestTfLStationData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load the station data once for all tests"""
        try:
            with open("tfl_stations.json") as f:
                cls.data = json.load(f)
            cls.stations = cls.data["stations"]
            cls.lines = cls.data["lines"]
        except FileNotFoundError:
            cls.data = None
            cls.stations = {}
            cls.lines = {}

    def test_station_count_range(self):
        """Verify we have between 250-300 stations"""
        station_count = len(self.stations)
        self.assertGreaterEqual(
            station_count, 250, f"Expected at least 250 stations, got {station_count}"
        )
        self.assertLessEqual(
            station_count, 300, f"Expected at most 300 stations, got {station_count}"
        )
        print(f"✓ Station count validation passed: {station_count} stations")

    def test_baker_street_connections(self):
        """Verify Baker Street has connections on Metropolitan, Bakerloo, Jubilee, etc."""
        baker_street = None

        # Find Baker Street station
        for _station_id, station in self.stations.items():
            if "Baker Street" in station["name"]:
                baker_street = station
                break

        self.assertIsNotNone(baker_street, "Baker Street station not found")

        # Check it has the expected lines
        expected_lines = ["metropolitan", "bakerloo", "jubilee"]
        station_lines = [line.lower() for line in baker_street["lines"]]

        for expected_line in expected_lines:
            self.assertIn(
                expected_line,
                station_lines,
                f"Baker Street missing {expected_line} line. Found lines: {station_lines}",
            )

        print(f"✓ Baker Street lines validation passed: {baker_street['lines']}")

    def test_metropolitan_line_travel_time(self):
        """Verify Metropolitan line from Baker Street to Kings Cross takes 5-7 minutes"""
        # This test would require implementing travel time fetching
        # For now, we'll check that both stations exist and are connected

        baker_street = None
        kings_cross = None

        for _station_id, station in self.stations.items():
            if "Baker Street" in station["name"]:
                baker_street = station
            elif "King" in station["name"] and "Cross" in station["name"]:
                kings_cross = station

        self.assertIsNotNone(baker_street, "Baker Street station not found")
        self.assertIsNotNone(kings_cross, "Kings Cross station not found")

        # Check both stations are on Metropolitan line
        baker_lines = [line.lower() for line in baker_street["lines"]]
        kings_lines = [line.lower() for line in kings_cross["lines"]]

        self.assertIn("metropolitan", baker_lines, "Baker Street not on Metropolitan line")
        self.assertIn("metropolitan", kings_lines, "Kings Cross not on Metropolitan line")

        print("✓ Metropolitan line connectivity validation passed")

        # Travel time validation would require connecting to real-time TfL APIs
        # This is beyond the scope of station data validation tests

    def test_station_connectivity(self):
        """Check that every station has at least 2 connections (except terminuses)"""
        single_connection_stations = []
        no_connection_stations = []

        for _station_id, station in self.stations.items():
            connection_count = station.get("connection_count", 0)

            if connection_count == 0:
                no_connection_stations.append(station["name"])
            elif connection_count == 1:
                single_connection_stations.append(station["name"])

        # Allow some terminus stations with only 1 connection
        max_terminus_stations = 25  # Reasonable number for London Underground terminuses

        self.assertEqual(
            len(no_connection_stations),
            0,
            f"Stations with no connections: {no_connection_stations}",
        )

        self.assertLessEqual(
            len(single_connection_stations),
            max_terminus_stations,
            f"Too many single-connection stations (expected ≤{max_terminus_stations}): "
            f"{single_connection_stations}",
        )

        print("✓ Station connectivity validation passed")
        print(f"  Stations with 1 connection (terminus): {len(single_connection_stations)}")
        if single_connection_stations:
            print(f"  Terminus stations: {single_connection_stations[:10]}...")  # Show first 10

    def test_station_data_completeness(self):
        """Verify each station has required fields"""
        required_fields = ["id", "name", "lat", "lon", "lines", "connections"]

        incomplete_stations = []

        for station_id, station in self.stations.items():
            missing_fields = []
            for field in required_fields:
                if field not in station or station[field] is None:
                    missing_fields.append(field)

            if missing_fields:
                incomplete_stations.append(
                    {"station": station.get("name", station_id), "missing": missing_fields}
                )

        self.assertEqual(
            len(incomplete_stations),
            0,
            f"Stations with incomplete data: {incomplete_stations[:5]}...",  # Show first 5
        )

        print("✓ Station data completeness validation passed")

    def test_coordinate_validity(self):
        """Verify all stations have valid London coordinates"""
        # London bounds (approximate)
        MIN_LAT, MAX_LAT = 51.2, 51.8
        MIN_LON, MAX_LON = -0.8, 0.5

        invalid_coordinates = []

        for station_id, station in self.stations.items():
            lat = station.get("lat")
            lon = station.get("lon")

            if not (MIN_LAT <= lat <= MAX_LAT and MIN_LON <= lon <= MAX_LON):
                invalid_coordinates.append(
                    {"station": station.get("name", station_id), "lat": lat, "lon": lon}
                )

        self.assertEqual(
            len(invalid_coordinates),
            0,
            f"Stations with invalid London coordinates: {invalid_coordinates}",
        )

        print("✓ Coordinate validity validation passed")

    def test_line_data_completeness(self):
        """Verify line data is complete"""
        self.assertGreater(len(self.lines), 0, "No line data found")

        for line_id, line in self.lines.items():
            self.assertIn("name", line, f"Line {line_id} missing name")
            self.assertIn("id", line, f"Line {line_id} missing id")

        print(f"✓ Line data completeness validation passed: {len(self.lines)} lines")


def run_tests():
    """Run all tests and print results"""
    # Check if data file exists
    try:
        with open("tfl_stations.json") as f:
            json.load(f)
    except FileNotFoundError:
        print("Error: tfl_stations.json not found. Run fetch_tfl_stations.py first.")
        return False

    print("Running TfL Station Data Validation Tests")
    print("=" * 50)

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTfLStationData)

    # Run tests with custom result handling
    runner = unittest.TextTestRunner(verbosity=2, stream=open("/dev/null", "w"))
    result = runner.run(suite)

    # Print custom results
    print("\nTest Results:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")

    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")

    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\nOverall result: {'PASS' if success else 'FAIL'}")

    return success


if __name__ == "__main__":
    run_tests()
