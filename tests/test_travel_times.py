# ABOUTME: Tests travel times between specific station pairs using TfL journey planner API
# ABOUTME: Validates Baker Street to Kings Cross and Preston Road to Baker Street journey times

import json

import requests

from fetch_tfl_stations import TfLStationFetcher


def find_station_by_name(stations_data, search_name):
    """Find station by partial name match"""
    for station_id, station in stations_data["stations"].items():
        if search_name.lower() in station["name"].lower():
            return station_id, station
    return None, None


def get_journey_time_detailed(from_station_id, to_station_id):
    """Get detailed journey information between two stations"""
    base_url = "https://api.tfl.gov.uk"

    # Try the correct endpoint format: /Journey/JourneyResults/{from}/to/{to}
    urls_to_try = [
        f"{base_url}/Journey/JourneyResults/{from_station_id}/to/{to_station_id}",
        f"{base_url}/Journey/JourneyResults/{from_station_id}/to/{to_station_id}?mode=tube",
        f"{base_url}/journey/journeyresults/{from_station_id}/to/{to_station_id}",
    ]

    for i, url in enumerate(urls_to_try):
        try:
            print(f"Attempt {i + 1}: {url}")
            response = requests.get(url)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if "journeys" in data and len(data["journeys"]) > 0:
                    journey = data["journeys"][0]
                    return {
                        "duration_minutes": journey.get("duration", 0),
                        "legs": len(journey.get("legs", [])),
                        "full_journey": journey,
                    }
            else:
                print(f"Error response: {response.text[:200]}")

        except Exception as e:
            print(f"Error in attempt {i + 1}: {e}")

    return None


def test_specific_journeys():
    """Test specific journey times mentioned in requirements"""
    # Load station data
    with open("tfl_stations.json") as f:
        stations_data = json.load(f)

    print("Testing specific journey times...")
    print("=" * 50)

    # Test 1: Baker Street to Kings Cross
    print("\n1. Baker Street to Kings Cross (Metropolitan line)")
    baker_id, baker_station = find_station_by_name(stations_data, "Baker Street")
    kings_id, kings_station = find_station_by_name(stations_data, "King's Cross")

    if baker_station and kings_station:
        print(f"From: {baker_station['name']} ({baker_id})")
        print(f"To: {kings_station['name']} ({kings_id})")
        print(f"Lines available at Baker Street: {baker_station['lines']}")
        print(f"Lines available at Kings Cross: {kings_station['lines']}")

        journey_info = get_journey_time_detailed(baker_id, kings_id)
        if journey_info:
            print(f"Journey time: {journey_info['duration_minutes']} minutes")
            print(f"Number of legs: {journey_info['legs']}")
        else:
            print("Could not get journey time via API")
    else:
        print("Could not find one of the stations")

    # Test 2: Preston Road to Baker Street
    print("\n2. Preston Road to Baker Street (Metropolitan line)")
    preston_id, preston_station = find_station_by_name(stations_data, "Preston Road")

    if preston_station and baker_station:
        print(f"From: {preston_station['name']} ({preston_id})")
        print(f"To: {baker_station['name']} ({baker_id})")
        print(f"Lines available at Preston Road: {preston_station['lines']}")
        print(f"Lines available at Baker Street: {baker_station['lines']}")

        journey_info = get_journey_time_detailed(preston_id, baker_id)
        if journey_info:
            print(f"Journey time: {journey_info['duration_minutes']} minutes")
            print(f"Number of legs: {journey_info['legs']}")
        else:
            print("Could not get journey time via API")
    else:
        print("Could not find one of the stations")

    # Test 3: Let's also check what stations we have
    print("\n3. Station search results:")
    search_terms = ["Baker Street", "King's Cross", "Preston Road"]
    for term in search_terms:
        matches = []
        for station_id, station in stations_data["stations"].items():
            if term.lower() in station["name"].lower():
                matches.append(f"{station['name']} ({station_id})")
        print(f"'{term}' matches: {matches}")


def test_journey_api_directly():
    """Test the journey API with different approaches"""
    print("\n" + "=" * 50)
    print("Testing TfL Journey API directly")
    print("=" * 50)

    base_url = "https://api.tfl.gov.uk"

    # Test different ways to specify stations
    test_queries = [
        "Baker Street to King's Cross using station names",
        "Baker Street Underground Station to King's Cross St. Pancras Underground Station",
        "Coordinates: Baker Street to King's Cross",
    ]

    station_names = [
        ("Baker Street", "King's Cross St. Pancras"),
        ("Baker Street Underground Station", "King's Cross St. Pancras Underground Station"),
        ("51.5226,-0.1571", "51.5308,-0.1238"),  # Approximate coordinates
    ]

    for i, (from_loc, to_loc) in enumerate(station_names):
        print(f"\n{i + 1}. {test_queries[i]}")

        params = {
            "from": from_loc,
            "to": to_loc,
        }

        try:
            response = requests.get(f"{base_url}/journey/journeyresults", params=params)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if "journeys" in data and len(data["journeys"]) > 0:
                    journey = data["journeys"][0]
                    duration = journey.get("duration", 0)
                    print(f"Duration: {duration} minutes")

                    # Print leg details
                    for j, leg in enumerate(journey.get("legs", [])):
                        mode = leg.get("mode", {}).get("name", "Unknown")
                        duration_leg = leg.get("duration", 0)
                        print(f"  Leg {j + 1}: {mode} ({duration_leg} min)")
                else:
                    print("No journeys found")
            else:
                print(f"Error: {response.text[:300]}")

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    test_specific_journeys()
    test_journey_api_directly()
