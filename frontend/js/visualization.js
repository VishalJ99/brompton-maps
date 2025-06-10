// Visualize route on the map
function visualizeRoute(route) {

    // Clear existing route layers
    clearRouteLayers();

    if (!route.path_coords || route.path_coords.length < 2) {
        console.error('Invalid route data for visualization:', route);
        return;
    }

    // Ensure app.routeLayers is initialized
    if (!Array.isArray(app.routeLayers)) {
        console.warn('Reinitializing app.routeLayers');
        app.routeLayers = [];
    }

    // Create route segments for each journey leg
    route.journey_legs.forEach((leg, index) => {
        try {
            visualizeJourneyLeg(leg, index);
        } catch (error) {
            console.error(`Error visualizing journey leg ${index}:`, error, leg);
        }
    });

    // Add start and end markers
    try {
        addRouteMarkers(route);
    } catch (error) {
        console.error('Error adding route markers:', error);
    }

    // Fit map to show entire route
    try {
        const bounds = getBoundsForCoordinates(route.path_coords);
        app.map.fitBounds(bounds, {
            padding: { top: 50, bottom: 50, left: 50, right: 50 },
            duration: 1000
        });
    } catch (error) {
        console.error('Error fitting map bounds:', error);
    }
}

// Visualize a single journey leg
function visualizeJourneyLeg(leg, index) {
    // Use timestamp to ensure unique layer IDs
    const timestamp = Date.now();
    const layerId = `route-leg-${index}-${timestamp}`;

    // Get coordinates for this leg
    const coordinates = getCoordinatesForLeg(leg);

    if (coordinates.length < 2) {
        console.warn('Not enough coordinates for leg:', leg);
        return;
    }

    // Create GeoJSON for the leg
    const legGeoJSON = {
        type: 'Feature',
        geometry: {
            type: 'LineString',
            coordinates: coordinates
        },
        properties: {
            mode: leg.mode,
            line: leg.line,
            color: leg.color || '#666666'
        }
    };

    try {
        // Add source
        app.map.addSource(layerId, {
            type: 'geojson',
            data: legGeoJSON
        });

        // Track the source
        app.routeLayers.push(layerId);

        // Add line layer with appropriate styling
        if (leg.mode === 'tube') {
            addTubeLineLayer(layerId, leg);
        } else if (leg.mode === 'bike') {
            addBikeLineLayer(layerId, leg);
        }

        // Add animated dots for active routes
        addAnimatedDots(layerId, leg);
    } catch (error) {
        console.error(`Error adding layers for leg ${index}:`, error);
        // Clean up if there was an error
        if (app.map.getSource(layerId)) {
            app.map.removeSource(layerId);
        }
        // Remove from tracking
        const idx = app.routeLayers.indexOf(layerId);
        if (idx > -1) {
            app.routeLayers.splice(idx, 1);
        }
    }
}

// Get coordinates for a journey leg
function getCoordinatesForLeg(leg) {
    const coords = [];

    // For journey legs, we want to trace through all intermediate stations
    // to show the actual tube line path instead of a straight line

    if (leg.segments && leg.segments.length > 0) {
        // Use segments data to trace through each station-to-station hop
        leg.segments.forEach((segment, index) => {
            // Add the 'from' station coordinates for the first segment
            if (index === 0 && segment.from_coords) {
                coords.push([segment.from_coords.lon, segment.from_coords.lat]);
            }

            // Always add the 'to' station coordinates
            if (segment.to_coords) {
                coords.push([segment.to_coords.lon, segment.to_coords.lat]);
            }
        });
    } else {
        // Fallback to direct connection if segments data is not available
        if (leg.from_coords) {
            coords.push([leg.from_coords.lon, leg.from_coords.lat]);
        }
        if (leg.to_coords) {
            coords.push([leg.to_coords.lon, leg.to_coords.lat]);
        }
    }

    return coords;
}

// Add tube line layer
function addTubeLineLayer(layerId, leg) {
    app.map.addLayer({
        id: layerId,
        type: 'line',
        source: layerId,
        layout: {
            'line-join': 'round',
            'line-cap': 'round'
        },
        paint: {
            'line-color': leg.color || '#666666',
            'line-width': [
                'interpolate',
                ['linear'],
                ['zoom'],
                10, 3,
                15, 8
            ],
            'line-opacity': 0.8
        }
    });

    // Add a white background line for better visibility
    const bgLayerId = `${layerId}-bg`;
    app.map.addLayer({
        id: bgLayerId,
        type: 'line',
        source: layerId,
        layout: {
            'line-join': 'round',
            'line-cap': 'round'
        },
        paint: {
            'line-color': '#ffffff',
            'line-width': [
                'interpolate',
                ['linear'],
                ['zoom'],
                10, 5,
                15, 12
            ],
            'line-opacity': 0.6
        }
    }, layerId);

    // Track the background layer
    app.routeLayers.push(bgLayerId);
}

// Add bike line layer (for future use)
function addBikeLineLayer(layerId, leg) {
    app.map.addLayer({
        id: layerId,
        type: 'line',
        source: layerId,
        layout: {
            'line-join': 'round',
            'line-cap': 'round'
        },
        paint: {
            'line-color': '#00a652',
            'line-width': [
                'interpolate',
                ['linear'],
                ['zoom'],
                10, 3,
                15, 6
            ],
            'line-dasharray': [2, 1],
            'line-opacity': 0.8
        }
    });
}

// Add animated dots along the route
function addAnimatedDots(layerId, leg) {
    const animLayerId = `${layerId}-animated`;

    try {
        // Add a pulsing dot layer
        app.map.addLayer({
            id: animLayerId,
            type: 'circle',
            source: layerId,
            paint: {
                'circle-radius': [
                    'interpolate',
                    ['linear'],
                    ['zoom'],
                    10, 2,
                    15, 4
                ],
                'circle-color': leg.color || '#666666',
                'circle-opacity': 0
            }
        });

        // Track the animated layer
        app.routeLayers.push(animLayerId);

        // Animate the dots
        let step = 0;
        let animationId = null;

        function animateDots() {
            step = (step + 1) % 100;
            const opacity = Math.sin(step * 0.05) * 0.5 + 0.5;

            if (app.map.getLayer(animLayerId)) {
                try {
                    app.map.setPaintProperty(animLayerId, 'circle-opacity', opacity);
                    animationId = requestAnimationFrame(animateDots);
                } catch (error) {
                    console.error('Error in animation:', error);
                    if (animationId) {
                        cancelAnimationFrame(animationId);
                    }
                }
            }
        }

        // Start animation
        animateDots();
    } catch (error) {
        console.error('Error adding animated dots:', error);
    }
}

// Add markers for route start and end
function addRouteMarkers(route) {
    app.routeMarkers = [];

    // Start marker
    const startCoords = route.path_coords[0];
    const startMarker = new mapboxgl.Marker({
        color: '#00a652',
        scale: 1.2
    })
        .setLngLat([startCoords.lon, startCoords.lat])
        .setPopup(new mapboxgl.Popup().setHTML(`
            <h4>Start: ${startCoords.name}</h4>
        `))
        .addTo(app.map);

    app.routeMarkers.push(startMarker);

    // End marker
    const endCoords = route.path_coords[route.path_coords.length - 1];
    const endMarker = new mapboxgl.Marker({
        color: '#e32017',
        scale: 1.2
    })
        .setLngLat([endCoords.lon, endCoords.lat])
        .setPopup(new mapboxgl.Popup().setHTML(`
            <h4>End: ${endCoords.name}</h4>
        `))
        .addTo(app.map);

    app.routeMarkers.push(endMarker);

    // Add intermediate stop markers for line changes
    if (route.journey_legs.length > 1) {
        for (let i = 0; i < route.journey_legs.length - 1; i++) {
            const leg = route.journey_legs[i];
            const nextLeg = route.journey_legs[i + 1];

            // If line changes, add a marker
            if (leg.line !== nextLeg.line) {
                const changeMarker = new mapboxgl.Marker({
                    color: '#ff9500',
                    scale: 0.8
                })
                    .setLngLat([leg.to_coords.lon, leg.to_coords.lat])
                    .setPopup(new mapboxgl.Popup().setHTML(`
                        <h4>${leg.to_name}</h4>
                        <p>Change from ${formatLineName(leg.line)} to ${formatLineName(nextLeg.line)}</p>
                    `))
                    .addTo(app.map);

                app.routeMarkers.push(changeMarker);
            }
        }
    }
}

// Create route animation (for future enhancement)
function animateRoute(route) {
    // This could be used to show the route progressing
    // For now, just a placeholder for future implementation
    // Route animation not yet implemented
}

// Export route as image (for future enhancement)
function exportRouteImage() {
    // Get map canvas
    const canvas = app.map.getCanvas();

    // Convert to blob and download
    canvas.toBlob((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'brompton-route.png';
        a.click();
        URL.revokeObjectURL(url);
    });
}

// Visualize multi-modal route (bike + tube)
function visualizeMultiModalRoute(route) {

    // Clear existing route layers
    clearRouteLayers();

    if (!route.segments || route.segments.length === 0) {
        console.error('Invalid route data for visualization:', route);
        return;
    }

    // Ensure app.routeLayers is initialized
    if (!Array.isArray(app.routeLayers)) {
        console.warn('Reinitializing app.routeLayers');
        app.routeLayers = [];
    }

    // Process each segment
    route.segments.forEach((segment, index) => {
        try {
            if (segment.type === 'bike') {
                if (segment.geometry) {
                    visualizeBikeSegment(segment, index);
                }
            } else if (segment.type === 'tube') {
                visualizeTubeSegment(segment, index);
            }
            // Line changes are informational only, no visualization needed
        } catch (error) {
            console.error(`Error visualizing segment ${index}:`, error);
        }
    });

    // Add start and end markers
    try {
        addMultiModalRouteMarkers(route);
    } catch (error) {
        console.error('Error adding multi-modal route markers:', error);
    }

    // Fit map to show entire route
    try {
        const bounds = new mapboxgl.LngLatBounds();
        let hasCoordinates = false;

        route.segments.forEach(segment => {
            if (segment.type === 'bike' && segment.geometry) {
                segment.geometry.forEach(coord => {
                    bounds.extend(coord);
                    hasCoordinates = true;
                });
            } else if (segment.type === 'tube') {
                // Add tube segment coordinates to bounds as well
                const fromStation = app.stations.find(s => s.name === segment.from_name ||
                                                         s.id === segment.from_station);
                const toStation = app.stations.find(s => s.name === segment.to_name ||
                                                       s.id === segment.to_station);
                if (fromStation) {
                    bounds.extend([fromStation.lon, fromStation.lat]);
                    hasCoordinates = true;
                }
                if (toStation) {
                    bounds.extend([toStation.lon, toStation.lat]);
                    hasCoordinates = true;
                }
            }
        });

        if (hasCoordinates) {
            app.map.fitBounds(bounds, {
                padding: { top: 50, bottom: 50, left: 50, right: 50 },
                duration: 1000
            });
        }
    } catch (error) {
        console.error('Error fitting map bounds:', error);
    }
}

// Visualize bike segment with OSRM geometry
function visualizeBikeSegment(segment, index) {
    // Use timestamp to ensure unique layer IDs
    const timestamp = Date.now();
    const layerId = `bike-segment-${index}-${timestamp}`;

    // Create GeoJSON for bike path
    const bikeGeoJSON = {
        type: 'Feature',
        geometry: {
            type: 'LineString',
            coordinates: segment.geometry
        },
        properties: {
            mode: 'bike',
            duration: segment.duration_minutes,
            distance: segment.distance_km
        }
    };

    try {
        // Add source
        app.map.addSource(layerId, {
            type: 'geojson',
            data: bikeGeoJSON
        });

        // Track the source
        app.routeLayers.push(layerId);

        // Add background line (white)
        const bgLayerId = `${layerId}-bg`;
        app.map.addLayer({
            id: bgLayerId,
            type: 'line',
            source: layerId,
            layout: {
                'line-join': 'round',
                'line-cap': 'round'
            },
            paint: {
                'line-color': '#ffffff',
                'line-width': [
                    'interpolate',
                    ['linear'],
                    ['zoom'],
                    10, 5,
                    15, 10
                ],
                'line-opacity': 0.8
            }
        });
        app.routeLayers.push(bgLayerId);

        // Add bike line (dashed green)
        app.map.addLayer({
            id: layerId,
            type: 'line',
            source: layerId,
            layout: {
                'line-join': 'round',
                'line-cap': 'round'
            },
            paint: {
                'line-color': '#4CAF50',
                'line-width': [
                    'interpolate',
                    ['linear'],
                    ['zoom'],
                    10, 3,
                    15, 6
                ],
                'line-dasharray': [2, 1],
                'line-opacity': 0.9
            }
        });
    } catch (error) {
        console.error(`Error adding bike segment ${index}:`, error);
        // Clean up if there was an error
        if (app.map.getSource(layerId)) {
            app.map.removeSource(layerId);
        }
        // Remove from tracking
        const idx = app.routeLayers.indexOf(layerId);
        if (idx > -1) {
            app.routeLayers.splice(idx, 1);
        }
    }
}

// Visualize tube segment
function visualizeTubeSegment(segment, index) {
    // Use timestamp to ensure unique layer IDs
    const timestamp = Date.now();
    const layerId = `tube-segment-${index}-${timestamp}`;

    // For tube segments, we need to get station coordinates
    // This is a simplified version - in production, you'd want to trace actual tube paths
    const fromStation = app.stations.find(s => s.name === segment.from_name ||
                                             s.id === segment.from_station);
    const toStation = app.stations.find(s => s.name === segment.to_name ||
                                           s.id === segment.to_station);

    if (!fromStation || !toStation) {
        console.error('Could not find station coordinates for tube segment');
        return;
    }

    const coordinates = [
        [fromStation.lon, fromStation.lat],
        [toStation.lon, toStation.lat]
    ];

    // Create GeoJSON
    const tubeGeoJSON = {
        type: 'Feature',
        geometry: {
            type: 'LineString',
            coordinates: coordinates
        },
        properties: {
            mode: 'tube',
            line: segment.line,
            duration: segment.duration_minutes
        }
    };

    try {
        // Add source
        app.map.addSource(layerId, {
            type: 'geojson',
            data: tubeGeoJSON
        });

        // Track the source
        app.routeLayers.push(layerId);

        // Get line color
        const lineColor = getLineColor(segment.line);

        // Add background line
        const bgLayerId = `${layerId}-bg`;
        app.map.addLayer({
            id: bgLayerId,
            type: 'line',
            source: layerId,
            layout: {
                'line-join': 'round',
                'line-cap': 'round'
            },
            paint: {
                'line-color': '#ffffff',
                'line-width': [
                    'interpolate',
                    ['linear'],
                    ['zoom'],
                    10, 5,
                    15, 12
                ],
                'line-opacity': 0.6
            }
        });
        app.routeLayers.push(bgLayerId);

        // Add tube line
        app.map.addLayer({
            id: layerId,
            type: 'line',
            source: layerId,
            layout: {
                'line-join': 'round',
                'line-cap': 'round'
            },
            paint: {
                'line-color': lineColor,
                'line-width': [
                    'interpolate',
                    ['linear'],
                    ['zoom'],
                    10, 3,
                    15, 8
                ],
                'line-opacity': 0.8
            }
        });
    } catch (error) {
        console.error(`Error adding tube segment ${index}:`, error);
        // Clean up if there was an error
        if (app.map.getSource(layerId)) {
            app.map.removeSource(layerId);
        }
        // Remove from tracking
        const idx = app.routeLayers.indexOf(layerId);
        if (idx > -1) {
            app.routeLayers.splice(idx, 1);
        }
    }
}

// Add markers for multi-modal route
function addMultiModalRouteMarkers(route) {
    app.routeMarkers = app.routeMarkers || [];

    // Clear existing route markers
    app.routeMarkers.forEach(marker => marker.remove());
    app.routeMarkers = [];

    // Clear coordinate markers since we'll use route markers
    if (app.coordinateMarkers.start) {
        app.coordinateMarkers.start.remove();
        app.coordinateMarkers.start = null;
    }
    if (app.coordinateMarkers.end) {
        app.coordinateMarkers.end.remove();
        app.coordinateMarkers.end = null;
    }

    if (!route.segments || route.segments.length === 0) {
        console.warn('No segments in route for markers');
        return;
    }

    // Get first and last segments
    const firstSegment = route.segments[0];
    const lastSegment = route.segments[route.segments.length - 1];

    // Start marker
    if (firstSegment.type === 'bike' && firstSegment.geometry && firstSegment.geometry.length > 0) {
        const startCoord = firstSegment.geometry[0];
        const startMarker = new mapboxgl.Marker({
            color: '#00a652',
            scale: 1.2
        })
            .setLngLat(startCoord)
            .setPopup(new mapboxgl.Popup().setHTML(`
                <h4>Start: ${firstSegment.from_name}</h4>
            `))
            .addTo(app.map);

        app.routeMarkers.push(startMarker);
    }

    // End marker (avoid duplicate if there's only one segment)
    if (route.segments.length > 1 && lastSegment.type === 'bike' && lastSegment.geometry && lastSegment.geometry.length > 0) {
        const endCoord = lastSegment.geometry[lastSegment.geometry.length - 1];
        const endMarker = new mapboxgl.Marker({
            color: '#e32017',
            scale: 1.2
        })
            .setLngLat(endCoord)
            .setPopup(new mapboxgl.Popup().setHTML(`
                <h4>End: ${lastSegment.to_name}</h4>
            `))
            .addTo(app.map);

        app.routeMarkers.push(endMarker);
    } else if (route.segments.length === 1 && firstSegment.type === 'bike' && firstSegment.geometry && firstSegment.geometry.length > 0) {
        // For single segment (direct bike route), add end marker at the last coordinate
        const endCoord = firstSegment.geometry[firstSegment.geometry.length - 1];
        const endMarker = new mapboxgl.Marker({
            color: '#e32017',
            scale: 1.2
        })
            .setLngLat(endCoord)
            .setPopup(new mapboxgl.Popup().setHTML(`
                <h4>End: ${firstSegment.to_name}</h4>
            `))
            .addTo(app.map);

        app.routeMarkers.push(endMarker);
    }

    // Add markers for mode changes (bike to tube transitions)
    route.segments.forEach((segment, i) => {
        if (i > 0 && i < route.segments.length) {
            const prevSegment = route.segments[i - 1];

            // Mark bike->tube transitions
            if (prevSegment.type === 'bike' && segment.type === 'tube') {
                const station = app.stations.find(s => s.name === segment.from_name ||
                                                     s.id === segment.from_station);
                if (station) {
                    const transitionMarker = new mapboxgl.Marker({
                        color: '#ff9500',
                        scale: 0.8
                    })
                        .setLngLat([station.lon, station.lat])
                        .setPopup(new mapboxgl.Popup().setHTML(`
                            <h4>${segment.from_name}</h4>
                            <p>Switch from bike to ${formatLineName(segment.line)} line</p>
                        `))
                        .addTo(app.map);

                    app.routeMarkers.push(transitionMarker);
                }
            }

            // Mark tube->bike transitions
            if (prevSegment.type === 'tube' && segment.type === 'bike') {
                const station = app.stations.find(s => s.name === segment.from_name ||
                                                     s.id === prevSegment.to_station);
                if (station) {
                    const transitionMarker = new mapboxgl.Marker({
                        color: '#ff9500',
                        scale: 0.8
                    })
                        .setLngLat([station.lon, station.lat])
                        .setPopup(new mapboxgl.Popup().setHTML(`
                            <h4>${segment.from_name}</h4>
                            <p>Switch from ${formatLineName(prevSegment.line)} line to bike</p>
                        `))
                        .addTo(app.map);

                    app.routeMarkers.push(transitionMarker);
                }
            }
        }
    });
}
