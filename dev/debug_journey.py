# ABOUTME: CLI debugging tool for TfL journey time API calls
# ABOUTME: Takes station names as arguments and shows detailed API response for troubleshooting

import json
import sys

import requests

from tfl_utils import TfLStationUtils


def debug_journey(station1: str, station2: str):
    """Debug journey time API call with detailed output"""
    print(f"Debugging journey: {station1} → {station2}")
    print("=" * 60)

    utils = TfLStationUtils()

    # Find stations
    print("1. Finding stations...")
    from_id, from_data = utils.find_station_by_name(station1)
    to_id, to_data = utils.find_station_by_name(station2)

    if not from_id:
        print(f"❌ Source station '{station1}' not found")
        return False

    if not to_id:
        print(f"❌ Destination station '{station2}' not found")
        return False

    print(f"✓ From: {from_data['name']} (ID: {from_id})")
    print(f"✓ To: {to_data['name']} (ID: {to_id})")

    # Check station details
    print("\n2. Station details...")
    print(f"From station lines: {from_data.get('lines', [])}")
    print(f"To station lines: {to_data.get('lines', [])}")

    # Check for common lines
    common_lines = utils.get_common_lines(station1, station2)
    print(f"Common lines: {common_lines}")

    # Make raw API call
    print("\n3. Making API call...")
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{from_id}/to/{to_id}"
    print(f"URL: {url}")

    try:
        response = requests.get(url)
        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✓ API call successful")

            # Check for journeys
            if "journeys" in data and len(data["journeys"]) > 0:
                journey = data["journeys"][0]
                duration = journey.get("duration", 0)
                legs = journey.get("legs", [])

                print(f"✓ Journey found: {duration} minutes")
                print(f"✓ Number of legs: {len(legs)}")

                # Show leg details
                print("\n4. Journey details:")
                for i, leg in enumerate(legs, 1):
                    print(f"  Leg {i}:")
                    print(f"    Mode: {leg.get('mode', {}).get('name', 'Unknown')}")
                    print(f"    Duration: {leg.get('duration', 0)} minutes")
                    if "departurePoint" in leg:
                        print(f"    From: {leg['departurePoint'].get('commonName', 'Unknown')}")
                    if "arrivalPoint" in leg:
                        print(f"    To: {leg['arrivalPoint'].get('commonName', 'Unknown')}")

                return True
            else:
                print("❌ No journeys found in response")
                print(f"Response keys: {list(data.keys())}")

                # Check for error messages
                if "message" in data:
                    print(f"API message: {data['message']}")

                return False
        else:
            print(f"❌ API error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error response: {json.dumps(error_data, indent=2)}")
            except json.JSONDecodeError:
                print(f"Error text: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False


def main():
    """Main CLI function"""
    if len(sys.argv) != 3:
        print("Usage: python debug_journey.py <station1> <station2>")
        print("Example: python debug_journey.py 'Baker Street' 'Kings Cross'")
        sys.exit(1)

    station1 = sys.argv[1]
    station2 = sys.argv[2]

    success = debug_journey(station1, station2)

    print(f"\n{'✓ SUCCESS' if success else '❌ FAILED'}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
