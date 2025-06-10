# ABOUTME: Analyzes the distribution of connections in the TFL stations JSON file
# ABOUTME: Helps diagnose why the graph has fewer edges than expected

import json


with open("tfl_stations.json") as f:
    data = json.load(f)

stations = data["stations"]
total_connections = 0
connection_counts = {}

for _station_id, station in stations.items():
    connections = station.get("connections", [])
    total_connections += len(connections)
    connection_counts[len(connections)] = connection_counts.get(len(connections), 0) + 1

print(f"Total stations: {len(stations)}")
print(f"Total connections in JSON: {total_connections}")
print(f"Average connections per station: {total_connections / len(stations):.2f}")
print("\nConnection count distribution:")
for count, num_stations in sorted(connection_counts.items()):
    print(f"  {count} connections: {num_stations} stations")

# Check for duplicate connections within a station
print("\nChecking for stations with duplicate connections...")
duplicate_count = 0
for _station_id, station in stations.items():
    connections = station.get("connections", [])
    to_stations = [c["to_station"] for c in connections]
    if len(to_stations) != len(set(to_stations)):
        print(
            f"  {station['name']}: {len(to_stations)} connections, {len(set(to_stations))} unique"
        )
        duplicate_count += 1

if duplicate_count == 0:
    print("  No duplicate connections found")

# Sample a multi-line station like Baker Street
print("\nSample: Baker Street connections:")
baker_st = stations.get("940GZZLUBST")
if baker_st:
    print(f"  Total connections: {len(baker_st.get('connections', []))}")
    for conn in baker_st.get("connections", []):
        to_station = stations.get(conn["to_station"])
        if to_station:
            print(f"    → {to_station['name']} ({conn['line']}, {conn['direction']})")
