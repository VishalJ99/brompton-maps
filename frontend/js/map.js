// Mapbox access token - loaded from config.js (not tracked in git)
mapboxgl.accessToken = CONFIG.MAPBOX_ACCESS_TOKEN;

// Initialize the map
function initializeMap() {
    // Create map centered on London
    app.map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/light-v11',
        center: [-0.1278, 51.5074], // London center
        zoom: 11,
        pitch: 0,
        bearing: 0
    });

    // Add navigation controls
    app.map.addControl(new mapboxgl.NavigationControl(), 'top-left');

    // Add fullscreen control
    app.map.addControl(new mapboxgl.FullscreenControl(), 'top-left');

    // When map loads, add stations
    app.map.on('load', () => {
        addStationMarkers();
        setupMapInteractions();
    });
}

// Add station markers to the map
function addStationMarkers() {
    if (!app.stations || app.stations.length === 0) {
        console.warn('No stations to display');
        return;
    }

    // Create a GeoJSON feature collection for stations
    const stationsGeoJSON = {
        type: 'FeatureCollection',
        features: app.stations.map(station => ({
            type: 'Feature',
            geometry: {
                type: 'Point',
                coordinates: [station.lon, station.lat]
            },
            properties: {
                id: station.id,
                name: station.name,
                lines: station.lines.join(', '),
                primaryLine: station.lines[0],
                zone: station.zone
            }
        }))
    };

    // Add source
    app.map.addSource('stations', {
        type: 'geojson',
        data: stationsGeoJSON
    });

    // Add layer for station circles
    app.map.addLayer({
        id: 'station-circles',
        type: 'circle',
        source: 'stations',
        paint: {
            'circle-radius': [
                'interpolate',
                ['linear'],
                ['zoom'],
                10, 4,
                15, 8
            ],
            'circle-color': [
                'case',
                ['==', ['get', 'primaryLine'], 'bakerloo'], '#B36305',
                ['==', ['get', 'primaryLine'], 'central'], '#E32017',
                ['==', ['get', 'primaryLine'], 'circle'], '#FFD300',
                ['==', ['get', 'primaryLine'], 'district'], '#00782A',
                ['==', ['get', 'primaryLine'], 'hammersmith-city'], '#F3A9BB',
                ['==', ['get', 'primaryLine'], 'jubilee'], '#A0A5A9',
                ['==', ['get', 'primaryLine'], 'metropolitan'], '#9B0056',
                ['==', ['get', 'primaryLine'], 'northern'], '#000000',
                ['==', ['get', 'primaryLine'], 'piccadilly'], '#003688',
                ['==', ['get', 'primaryLine'], 'victoria'], '#0098D4',
                ['==', ['get', 'primaryLine'], 'waterloo-city'], '#95CDBA',
                '#666666' // default color
            ],
            'circle-stroke-color': '#ffffff',
            'circle-stroke-width': 2,
            'circle-opacity': 0.9
        }
    });

    // Add layer for station labels
    app.map.addLayer({
        id: 'station-labels',
        type: 'symbol',
        source: 'stations',
        layout: {
            'text-field': ['get', 'name'],
            'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
            'text-size': [
                'interpolate',
                ['linear'],
                ['zoom'],
                10, 0,
                12, 10,
                15, 14
            ],
            'text-offset': [0, 1.5],
            'text-anchor': 'top'
        },
        paint: {
            'text-color': '#333',
            'text-halo-color': '#fff',
            'text-halo-width': 1.5
        }
    });
}

// Set up map interactions
function setupMapInteractions() {
    // Change cursor on hover
    app.map.on('mouseenter', 'station-circles', () => {
        app.map.getCanvas().style.cursor = 'pointer';
    });

    app.map.on('mouseleave', 'station-circles', () => {
        app.map.getCanvas().style.cursor = '';
    });

    // Click handler for stations
    app.map.on('click', 'station-circles', (e) => {
        if (e.features.length > 0) {
            const feature = e.features[0];
            const coordinates = feature.geometry.coordinates.slice();
            const properties = feature.properties;

            // Create popup
            new mapboxgl.Popup()
                .setLngLat(coordinates)
                .setHTML(`
                    <h4>${properties.name}</h4>
                    <p><strong>Lines:</strong> ${properties.lines}</p>
                    ${properties.zone ? `<p><strong>Zone:</strong> ${properties.zone}</p>` : ''}
                `)
                .addTo(app.map);
        }
    });
}

// Highlight a specific station
function highlightStation(station) {
    // Fly to station
    app.map.flyTo({
        center: [station.lon, station.lat],
        zoom: 14,
        duration: 1000
    });

    // Add temporary highlight marker
    if (app.highlightMarker) {
        app.highlightMarker.remove();
    }

    app.highlightMarker = new mapboxgl.Marker({
        color: '#ff0000'
    })
        .setLngLat([station.lon, station.lat])
        .addTo(app.map);

    // Remove highlight after 3 seconds
    setTimeout(() => {
        if (app.highlightMarker) {
            app.highlightMarker.remove();
            app.highlightMarker = null;
        }
    }, 3000);
}

// Clear all route layers from the map
function clearRouteLayers() {
    // Ensure routeLayers is always an array
    if (!Array.isArray(app.routeLayers)) {
        app.routeLayers = [];
        return;
    }

    // Create a copy of the layer IDs to avoid modification during iteration
    const layerIds = [...app.routeLayers];

    // Remove all route layers
    layerIds.forEach(layerId => {
        try {
            // Check if layer exists before removing
            if (app.map.getLayer(layerId)) {
                app.map.removeLayer(layerId);
            }

            // Check if source exists before removing
            // Note: Sources can only be removed if no layers are using them
            if (app.map.getSource(layerId)) {
                // Double-check no layers are using this source
                const style = app.map.getStyle();
                const layersUsingSource = style.layers.filter(layer =>
                    layer.source === layerId
                );

                if (layersUsingSource.length === 0) {
                    app.map.removeSource(layerId);
                }
            }
        } catch (error) {
            console.error(`Error removing layer/source ${layerId}:`, error);
        }
    });

    // Reset the array
    app.routeLayers = [];

    // Remove route markers
    if (app.routeMarkers && Array.isArray(app.routeMarkers)) {
        app.routeMarkers.forEach(marker => {
            try {
                marker.remove();
            } catch (error) {
                console.error('Error removing marker:', error);
            }
        });
        app.routeMarkers = [];
    }
}

// Get bounds for a set of coordinates
function getBoundsForCoordinates(coords) {
    const bounds = new mapboxgl.LngLatBounds();

    coords.forEach(coord => {
        bounds.extend([coord.lon || coord[0], coord.lat || coord[1]]);
    });

    return bounds;
}

// Create a smooth curve between two points (for future bike routes)
function createCurvedLine(start, end, offset = 0.1) {
    const midLng = (start[0] + end[0]) / 2;
    const midLat = (start[1] + end[1]) / 2;

    // Calculate perpendicular offset
    const dx = end[0] - start[0];
    const dy = end[1] - start[1];
    const dist = Math.sqrt(dx * dx + dy * dy);

    const offsetLng = midLng - (dy / dist) * offset;
    const offsetLat = midLat + (dx / dist) * offset;

    // Create smooth curve with more points
    const points = [];
    for (let t = 0; t <= 1; t += 0.1) {
        const t2 = t * t;
        const mt = 1 - t;
        const mt2 = mt * mt;

        const lng = mt2 * start[0] + 2 * mt * t * offsetLng + t2 * end[0];
        const lat = mt2 * start[1] + 2 * mt * t * offsetLat + t2 * end[1];

        points.push([lng, lat]);
    }

    return points;
}

// Enable coordinate selection mode
function enableCoordinateSelection() {
    app.selectingCoordinate = 'start';
    app.map.getCanvas().style.cursor = 'crosshair';

    // Remove existing click handler if any
    app.map.off('click', handleCoordinateClick);

    // Add click handler for coordinate selection
    app.map.on('click', handleCoordinateClick);
}

// Disable coordinate selection mode
function disableCoordinateSelection() {
    app.selectingCoordinate = null;
    app.map.getCanvas().style.cursor = '';
    app.map.off('click', handleCoordinateClick);
}

// Handle map click for coordinate selection
function handleCoordinateClick(e) {
    if (app.inputMode !== 'coordinates' || !app.selectingCoordinate) return;

    const lngLat = e.lngLat;
    const coords = [lngLat.lng, lngLat.lat];

    if (app.selectingCoordinate === 'start') {
        document.getElementById('from-lat').value = lngLat.lat.toFixed(4);
        document.getElementById('from-lon').value = lngLat.lng.toFixed(4);
        document.getElementById('from-address').value = `${lngLat.lat.toFixed(4)}, ${lngLat.lng.toFixed(4)}`;
        updateCoordinateMarker('start', coords);
        app.selectedPlaces.from = {
            name: `${lngLat.lat.toFixed(4)}, ${lngLat.lng.toFixed(4)}`,
            lat: lngLat.lat,
            lng: lngLat.lng
        };
        app.selectingCoordinate = 'end';
    } else {
        document.getElementById('to-lat').value = lngLat.lat.toFixed(4);
        document.getElementById('to-lon').value = lngLat.lng.toFixed(4);
        document.getElementById('to-address').value = `${lngLat.lat.toFixed(4)}, ${lngLat.lng.toFixed(4)}`;
        updateCoordinateMarker('end', coords);
        app.selectedPlaces.to = {
            name: `${lngLat.lat.toFixed(4)}, ${lngLat.lng.toFixed(4)}`,
            lat: lngLat.lat,
            lng: lngLat.lng
        };
        app.selectingCoordinate = 'start';
    }

    validateCoordinateInputs();
}

// Update coordinate marker on map
function updateCoordinateMarker(type, coords) {
    // Remove existing marker
    if (app.coordinateMarkers[type]) {
        app.coordinateMarkers[type].remove();
    }

    // Create new marker
    const color = type === 'start' ? '#00ff00' : '#ff0000';
    const marker = new mapboxgl.Marker({ color })
        .setLngLat(coords)
        .addTo(app.map);

    app.coordinateMarkers[type] = marker;
}
