// Main application state
const app = {
    // Use relative URL for API - works for both local and production
    apiUrl: '/api',
    stations: [],
    currentRoute: null,
    map: null,
    markers: {},
    routeLayers: [],  // Ensure this is always initialized as empty array
    routeMarkers: [], // Initialize route markers array
    inputMode: 'coordinates', // 'coordinates' or 'settings'
    coordinateMarkers: {
        start: null,
        end: null
    },
    selectingCoordinate: null, // 'start', 'end', or null
    // Google Places Autocomplete instances
    autocomplete: {
        from: null,
        to: null
    },
    // Selected places data
    selectedPlaces: {
        from: null,
        to: null
    },
    // Advanced settings
    settings: {
        stationAccessTime: 2.0,
        trainWaitingTime: 5.0,
        lineChangeTime: 5.0
    }
};

// Initialize application
document.addEventListener('DOMContentLoaded', async () => {
    // Load Google Maps Places API
    loadGoogleMapsAPI();

    // Check API status
    await checkApiStatus();

    // Load stations
    await loadStations();

    // Initialize map (defined in map.js)
    initializeMap();

    // Set up event listeners
    setupEventListeners();

    // Simple mobile detection for MVP
    const isMobile = window.innerWidth <= 768 || /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    if (isMobile) {
        console.log('Mobile device detected - using simple header UI');
    }

    // Enable coordinate selection since it's the default mode
    enableCoordinateSelection();
});

// Check API and graph status
async function checkApiStatus() {
    try {
        const response = await fetch(`${app.apiUrl}/graph/status`);
        const status = await response.json();

        updateStatusIndicator(status);
    } catch (error) {
        console.error('Failed to check API status:', error);
        updateStatusIndicator({ error: true });
    }
}

// Update status indicator
function updateStatusIndicator(status) {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');

    if (status.error) {
        statusDot.classList.remove('active');
        statusText.textContent = 'API connection failed';
    } else if (status.multilayer_router_loaded) {
        statusDot.classList.add('active');
        statusText.textContent = 'Multi-layer routing active (bike+tube)';
    } else if (status.tfl_graph_loaded) {
        statusDot.classList.add('active');
        if (status.merged_graph_loaded) {
            statusText.textContent = `Active: ${status.active_graph} graph (bike+tube ready)`;
        } else {
            statusText.textContent = 'Active: tube-only routing';
        }
    } else {
        statusDot.classList.remove('active');
        statusText.textContent = 'No graphs loaded';
    }
}

// Load stations from API
async function loadStations() {
    try {
        const response = await fetch(`${app.apiUrl}/stations`);
        const data = await response.json();

        if (data.stations) {
            app.stations = data.stations;
        }
    } catch (error) {
        console.error('Failed to load stations:', error);
    }
}

// Populate station select dropdowns (kept for completeness, not used)
function populateStationSelects() {
    // This function is no longer used but kept for potential future use
}

// Set up event listeners
function setupEventListeners() {
    // Find route button
    document.getElementById('find-route').addEventListener('click', findRoute);

    // Tab switching
    document.querySelectorAll('.tab-button').forEach(button => {
        button.addEventListener('click', (e) => {
            const mode = e.target.dataset.mode;
            switchInputMode(mode);
        });
    });

    // Address input handlers will be set up after Google Maps loads

    // Settings handlers
    document.getElementById('station-access-time').addEventListener('change', (e) => {
        app.settings.stationAccessTime = parseFloat(e.target.value);
    });

    document.getElementById('train-waiting-time').addEventListener('change', (e) => {
        app.settings.trainWaitingTime = parseFloat(e.target.value);
    });

    document.getElementById('line-change-time').addEventListener('change', (e) => {
        app.settings.lineChangeTime = parseFloat(e.target.value);
    });

    document.getElementById('reset-settings').addEventListener('click', () => {
        app.settings.stationAccessTime = 2.0;
        app.settings.trainWaitingTime = 5.0;
        app.settings.lineChangeTime = 5.0;
        document.getElementById('station-access-time').value = 2;
        document.getElementById('train-waiting-time').value = 5;
        document.getElementById('line-change-time').value = 5;
    });
}

// Find route based on current input mode
async function findRoute() {
    if (app.inputMode === 'coordinates') {
        await findRouteCoordinates();
    }
    // Don't find routes when in settings mode
}


// Find route between coordinates
async function findRouteCoordinates() {
    const fromLat = parseFloat(document.getElementById('from-lat').value);
    const fromLon = parseFloat(document.getElementById('from-lon').value);
    const toLat = parseFloat(document.getElementById('to-lat').value);
    const toLon = parseFloat(document.getElementById('to-lon').value);

    if (!fromLat || !fromLon || !toLat || !toLon) {
        alert('Please select both start and end locations');
        return;
    }

    // Show loading overlay
    showLoading(true);

    try {
        const response = await fetch(`${app.apiUrl}/route/coordinates`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                start_lat: fromLat,
                start_lon: fromLon,
                end_lat: toLat,
                end_lon: toLon,
                max_bike_minutes: 45.0,
                station_access_time: app.settings.stationAccessTime,
                train_waiting_time: app.settings.trainWaitingTime,
                line_change_time: app.settings.lineChangeTime
            }),
        });

        const result = await response.json();

        if (result.status === 'success' && result.route) {
            app.currentRoute = result.route;

            try {
                displayMultiModalRoute(result.route);

                // Ensure map is loaded before visualizing
                if (app.map && app.map.loaded()) {
                    visualizeMultiModalRoute(result.route);
                } else {
                    app.map.once('load', () => {
                        visualizeMultiModalRoute(result.route);
                    });
                }
            } catch (visualError) {
                console.error('Visualization error:', visualError);
                alert('Route found but visualization failed. Check console for details.');
            }
        } else {
            console.error('Route response:', result);
            alert(`Route not found: ${result.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Failed to find route:', error);
        alert('Failed to calculate route. Please try again.');
    } finally {
        showLoading(false);
    }
}

// Display route details in the control panel
function displayRoute(route) {
    const resultsDiv = document.getElementById('route-results');
    resultsDiv.innerHTML = '';

    // Route summary
    const summary = document.createElement('div');
    summary.className = 'route-summary';
    summary.innerHTML = `
        <h3>Journey Summary</h3>
        <div class="total-time">${formatDuration(route.total_duration_minutes)}</div>
        <div class="route-overview">
            ${route.path.length - 1} stops,
            ${route.journey_legs.length} ${route.journey_legs.length === 1 ? 'segment' : 'segments'}
        </div>
    `;
    resultsDiv.appendChild(summary);

    // Journey legs
    route.journey_legs.forEach((leg, index) => {
        const legDiv = createJourneyLegElement(leg, index);
        resultsDiv.appendChild(legDiv);
    });
}

// Create journey leg element
function createJourneyLegElement(leg, index) {
    const legDiv = document.createElement('div');
    legDiv.className = `journey-leg ${leg.mode}`;

    // Set line color as CSS variable
    if (leg.mode === 'tube' && leg.color) {
        legDiv.style.setProperty('--line-color', leg.color);
    }

    legDiv.innerHTML = `
        <div class="leg-header">
            <span class="leg-mode">${leg.mode === 'tube' ? '🚇' : '🚴'}</span>
            <span class="leg-line">${formatLineName(leg.line)}</span>
            <span class="leg-duration">${formatDuration(leg.duration_minutes)}</span>
        </div>
        <div class="leg-details">
            <div>From: <span class="station-name">${leg.from_name}</span></div>
            <div>To: <span class="station-name">${leg.to_name}</span></div>
            ${leg.station_count > 1 ? `<div>${leg.station_count} stops</div>` : ''}
        </div>
    `;

    return legDiv;
}

// Format duration in minutes to readable string
function formatDuration(minutes) {
    if (minutes < 1) {
        return '< 1 min';
    } else if (minutes < 60) {
        return `${Math.round(minutes)} min`;
    } else {
        const hours = Math.floor(minutes / 60);
        const mins = Math.round(minutes % 60);
        if (mins === 0) {
            return `${hours}h`;
        }
        return `${hours}h ${mins}m`;
    }
}

// Format line name for display
function formatLineName(line) {
    if (!line || line === 'Unknown') {
        return 'Tube';
    }

    // Capitalize first letter of each word
    return line.split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
}

// Show/hide loading overlay
function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (show) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}

// Switch between input modes
function switchInputMode(mode) {
    app.inputMode = mode;

    // Update tab buttons
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.toggle('active', button.dataset.mode === mode);
    });

    // Update input panels
    document.getElementById('coordinate-input').classList.toggle('active', mode === 'coordinates');
    document.getElementById('settings-input').classList.toggle('active', mode === 'settings');

    // Enable map clicking for coordinates mode
    if (mode === 'coordinates') {
        enableCoordinateSelection();
    } else {
        disableCoordinateSelection();
    }

    // Show/hide find route button based on mode
    document.getElementById('find-route').style.display = mode === 'coordinates' ? 'block' : 'none';
}

// Validate coordinate inputs
function validateCoordinateInputs() {
    const fromLat = document.getElementById('from-lat').value;
    const fromLon = document.getElementById('from-lon').value;
    const toLat = document.getElementById('to-lat').value;
    const toLon = document.getElementById('to-lon').value;

    const allFilled = fromLat && fromLon && toLat && toLon;
    document.getElementById('find-route').disabled = !allFilled;
}

// Load Google Maps API
function loadGoogleMapsAPI() {
    if (!CONFIG.GOOGLE_MAPS_API_KEY || CONFIG.GOOGLE_MAPS_API_KEY === 'YOUR_GOOGLE_MAPS_API_KEY_HERE') {
        console.warn('Google Maps API key not configured. Address search will not be available.');
        return;
    }

    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${CONFIG.GOOGLE_MAPS_API_KEY}&libraries=places&callback=initGooglePlaces`;
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
}

// Initialize Google Places Autocomplete
window.initGooglePlaces = function() {

    // Options to bias results to London area
    const autocompleteOptions = {
        bounds: {
            north: 51.7,
            south: 51.2,
            east: 0.3,
            west: -0.6
        },
        strictBounds: false,
        componentRestrictions: { country: 'gb' },
        fields: ['geometry', 'name', 'formatted_address']
    };

    // Initialize autocomplete for start location
    const fromInput = document.getElementById('from-address');
    if (fromInput) {
        app.autocomplete.from = new google.maps.places.Autocomplete(fromInput, autocompleteOptions);
        app.autocomplete.from.addListener('place_changed', () => handlePlaceSelect('from'));
    }

    // Initialize autocomplete for end location
    const toInput = document.getElementById('to-address');
    if (toInput) {
        app.autocomplete.to = new google.maps.places.Autocomplete(toInput, autocompleteOptions);
        app.autocomplete.to.addListener('place_changed', () => handlePlaceSelect('to'));
    }
};

// Handle place selection from autocomplete
function handlePlaceSelect(type) {
    const autocomplete = app.autocomplete[type];
    const place = autocomplete.getPlace();

    if (!place.geometry || !place.geometry.location) {
        console.error('No geometry found for selected place');
        return;
    }

    // Extract coordinates
    const lat = place.geometry.location.lat();
    const lng = place.geometry.location.lng();

    // Store selected place data
    app.selectedPlaces[type] = {
        name: place.name || place.formatted_address,
        lat: lat,
        lng: lng
    };

    // Update hidden coordinate inputs
    if (type === 'from') {
        document.getElementById('from-lat').value = lat;
        document.getElementById('from-lon').value = lng;
        updateCoordinateMarker('start', [lng, lat]);
    } else {
        document.getElementById('to-lat').value = lat;
        document.getElementById('to-lon').value = lng;
        updateCoordinateMarker('end', [lng, lat]);
    }

    // Validate inputs to enable/disable find route button
    validateCoordinateInputs();
}

// Preprocess segments to squash consecutive tube segments on same line
function preprocessSegments(segments) {
    const processed = [];
    let i = 0;

    while (i < segments.length) {
        const segment = segments[i];

        // If this is a tube segment, check if we can squash with following segments
        if (segment.type === 'tube') {
            let j = i + 1;
            let combinedDuration = segment.duration_minutes;
            let stopCount = 1;

            // Find consecutive tube segments on the same line
            while (j < segments.length &&
                   segments[j].type === 'tube' &&
                   segments[j].line === segment.line) {
                combinedDuration += segments[j].duration_minutes;
                stopCount++;
                j++;
            }

            // Create combined segment if we found multiple
            if (j > i + 1) {
                processed.push({
                    ...segment,
                    to_name: segments[j - 1].to_name,
                    to_station: segments[j - 1].to_station,
                    duration_minutes: combinedDuration,
                    stop_count: stopCount,
                    is_combined: true
                });
                i = j; // Skip the segments we combined
            } else {
                // Single segment, keep as is
                processed.push(segment);
                i++;
            }
        } else {
            // Not a tube segment, keep as is
            processed.push(segment);
            i++;
        }
    }

    return processed;
}

// Display multi-modal route (from coordinates endpoint)
function displayMultiModalRoute(route) {
    const resultsDiv = document.getElementById('route-results');
    resultsDiv.innerHTML = '';

    // Route summary
    const summary = document.createElement('div');
    summary.className = 'route-summary';

    // Build transit comparison text if available
    let transitComparisonHtml = '';
    if (route.transit_comparison && route.transit_comparison.duration_text) {
        transitComparisonHtml = `<div class="transit-comparison">without bike: ${route.transit_comparison.duration_text}</div>`;
    }

    summary.innerHTML = `
        <h3>Journey Summary</h3>
        <div class="total-time">${formatDuration(route.total_duration)}</div>
        ${transitComparisonHtml}
        <div class="route-overview">
            ${route.segments.length} ${route.segments.length === 1 ? 'segment' : 'segments'}
            ${route.is_direct_bike ? ' (Direct bike route)' : ''}
        </div>
    `;
    resultsDiv.appendChild(summary);

    // Check if route has any tube segments
    const hasTubeSegments = route.segments.some(seg => seg.type === 'tube');

    // Add train waiting time box if there are tube segments
    if (hasTubeSegments) {
        const waitingTimeDiv = document.createElement('div');
        waitingTimeDiv.className = 'train-waiting-time-box';
        waitingTimeDiv.innerHTML = `
            <div class="waiting-time-content">
                <span class="waiting-time-icon">⏱️</span>
                <span class="waiting-time-text">Train Waiting Time: ${app.settings.trainWaitingTime} minutes</span>
            </div>
        `;
        resultsDiv.appendChild(waitingTimeDiv);
    }

    // Preprocess segments to squash consecutive tube segments on same line
    const processedSegments = preprocessSegments(route.segments);

    // Journey segments
    processedSegments.forEach((segment, index) => {
        const segDiv = createMultiModalSegmentElement(segment, index);
        resultsDiv.appendChild(segDiv);
    });
}

// Create multi-modal segment element
function createMultiModalSegmentElement(segment, index) {
    const segDiv = document.createElement('div');
    segDiv.className = `journey-leg ${segment.type}`;

    let content = '';

    if (segment.type === 'bike') {
        let bufferText = '';
        if (segment.station_access_buffer_minutes > 0) {
            const accessTime = app.settings.stationAccessTime;
            const waitTime = app.settings.trainWaitingTime;
            const totalBuffer = Math.round(segment.station_access_buffer_minutes);

            // Determine which components are included based on the segment
            if (segment.from_name === 'Start Location' && segment.to_name !== 'End Location') {
                // Start -> Station: access + wait
                bufferText = ` (includes ${totalBuffer} min: ${accessTime} min station access + ${waitTime} min train wait)`;
            } else if (segment.from_name !== 'Start Location' && segment.to_name === 'End Location') {
                // Station -> End: exit only
                bufferText = ` (includes ${totalBuffer} min station exit)`;
            } else if (segment.from_name !== 'Start Location' && segment.to_name !== 'End Location') {
                // Station -> Station: exit + access + wait
                bufferText = ` (includes ${totalBuffer} min: ${accessTime} min exit + ${accessTime} min access + ${waitTime} min train wait)`;
            }
        }

        content = `
            <div class="leg-header">
                <span class="leg-mode">🚴</span>
                <span class="leg-line">Bike</span>
                <span class="leg-duration">${formatDuration(segment.duration_minutes)}</span>
            </div>
            <div class="leg-details">
                <div>From: <span class="station-name">${segment.from_name}</span></div>
                <div>To: <span class="station-name">${segment.to_name}</span></div>
                <div>${segment.distance_km.toFixed(1)} km${bufferText}</div>
            </div>
        `;
    } else if (segment.type === 'tube') {
        // Set line color as CSS variable
        const lineColor = getLineColor(segment.line);
        if (lineColor) {
            segDiv.style.setProperty('--line-color', lineColor);
        }

        const stopInfo = segment.is_combined ?
            `<div class="stop-count">${segment.stop_count} stops, ${formatDuration(segment.duration_minutes)}</div>` :
            `<div class="stop-count">${formatDuration(segment.duration_minutes)}</div>`;

        content = `
            <div class="leg-header">
                <span class="leg-mode">🚇</span>
                <span class="leg-line">${formatLineName(segment.line)}</span>
                <span class="leg-duration">${formatDuration(segment.duration_minutes)}</span>
            </div>
            <div class="leg-details">
                <div>From: <span class="station-name">${segment.from_name}</span></div>
                <div>To: <span class="station-name">${segment.to_name}</span></div>
                ${segment.is_combined ? `<div class="stop-info">${segment.stop_count} stops</div>` : ''}
            </div>
        `;
    } else if (segment.type === 'line_change') {
        content = `
            <div class="leg-header">
                <span class="leg-mode">🔄</span>
                <span class="leg-line">Line Change at ${segment.from_name}</span>
                <span class="leg-duration">${formatDuration(segment.duration_minutes)}</span>
            </div>
            <div class="leg-details">
                <div>From: <span style="color: ${getLineColor(segment.from_line)}">${formatLineName(segment.from_line)} Line</span></div>
                <div>To: <span style="color: ${getLineColor(segment.to_line)}">${formatLineName(segment.to_line)} Line</span></div>
                <div class="change-duration">Change time: ${segment.duration_minutes} minutes</div>
            </div>
        `;
    }

    segDiv.innerHTML = content;
    return segDiv;
}

// Get line color from API utils colors
function getLineColor(line) {
    if (!line) {
        return '#666666'; // Default gray for undefined lines
    }

    const colors = {
        'bakerloo': '#B36305',
        'central': '#E32017',
        'circle': '#FFD300',
        'district': '#00782A',
        'hammersmith-city': '#F3A9BB',
        'jubilee': '#A0A5A9',
        'metropolitan': '#9B0056',
        'northern': '#000000',
        'piccadilly': '#003688',
        'victoria': '#0098D4',
        'waterloo-city': '#95CDBA'
    };

    const normalized = line.toLowerCase().replace(' line', '').replace(' & ', '-');
    return colors[normalized] || '#666666';
}
