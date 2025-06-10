// Routing-specific functions

// Calculate alternative routes (for future enhancement)
async function findAlternativeRoutes(fromId, toId) {
    // Placeholder for finding alternative routes
    // Could implement k-shortest paths or different routing strategies
    // Alternative routes not yet implemented
    return [];
}

// Estimate journey time based on time of day (for future enhancement)
function adjustForTimeOfDay(route, departureTime) {
    // Placeholder for time-based adjustments
    // Could factor in peak hours, service frequency, etc.
    return route.total_duration_minutes;
}

// Compare tube-only vs bike+tube routes (for future enhancement)
async function compareRoutingModes(fromCoords, toCoords) {
    // Placeholder for comparing different routing modes
    // Will be implemented when bike+tube routing is available
    // Multi-modal comparison not yet implemented
    return null;
}

// Format route for sharing/export
function formatRouteForExport(route) {
    let output = 'Brompton Maps Route\n';
    output += '===================\n\n';

    output += `Total Time: ${formatDuration(route.total_duration_minutes)}\n`;
    output += `Stops: ${route.path.length - 1}\n\n`;

    output += 'Journey Details:\n';
    route.journey_legs.forEach((leg, index) => {
        output += `\n${index + 1}. ${leg.mode === 'tube' ? 'Tube' : 'Bike'}: `;
        output += `${formatDuration(leg.duration_minutes)}\n`;
        output += `   From: ${leg.from_name}\n`;
        output += `   To: ${leg.to_name}\n`;
        if (leg.line && leg.line !== 'Unknown') {
            output += `   Line: ${formatLineName(leg.line)}\n`;
        }
        if (leg.station_count > 1) {
            output += `   Stops: ${leg.station_count}\n`;
        }
    });

    return output;
}

// Share route via Web Share API
async function shareRoute(route) {
    const routeText = formatRouteForExport(route);

    if (navigator.share) {
        try {
            await navigator.share({
                title: 'Brompton Maps Route',
                text: routeText,
                url: window.location.href
            });
        } catch (err) {
            console.error('Error sharing:', err);
        }
    } else {
        // Fallback: copy to clipboard
        navigator.clipboard.writeText(routeText).then(() => {
            alert('Route copied to clipboard!');
        });
    }
}

// Save route to local storage
function saveRoute(route, name) {
    const savedRoutes = JSON.parse(localStorage.getItem('bromptonRoutes') || '[]');

    const routeData = {
        id: Date.now(),
        name: name || `Route ${savedRoutes.length + 1}`,
        date: new Date().toISOString(),
        from: route.journey_legs[0].from_name,
        to: route.journey_legs[route.journey_legs.length - 1].to_name,
        duration: route.total_duration_minutes,
        data: route
    };

    savedRoutes.push(routeData);
    localStorage.setItem('bromptonRoutes', JSON.stringify(savedRoutes));

    return routeData.id;
}

// Load saved routes
function loadSavedRoutes() {
    return JSON.parse(localStorage.getItem('bromptonRoutes') || '[]');
}

// Delete saved route
function deleteSavedRoute(routeId) {
    const savedRoutes = loadSavedRoutes();
    const filtered = savedRoutes.filter(r => r.id !== routeId);
    localStorage.setItem('bromptonRoutes', JSON.stringify(filtered));
}

// Get route statistics
function getRouteStatistics(route) {
    const stats = {
        totalTime: route.total_duration_minutes,
        totalStops: route.path.length - 1,
        lineChanges: 0,
        tubeTime: 0,
        bikeTime: 0,
        segments: route.journey_legs.length
    };

    // Calculate line changes and time breakdown
    let previousLine = null;
    route.journey_legs.forEach(leg => {
        if (leg.mode === 'tube') {
            stats.tubeTime += leg.duration_minutes;
            if (previousLine && previousLine !== leg.line) {
                stats.lineChanges++;
            }
            previousLine = leg.line;
        } else if (leg.mode === 'bike') {
            stats.bikeTime += leg.duration_minutes;
        }
    });

    return stats;
}

// URL handling for sharing routes
function encodeRouteToURL(fromId, toId) {
    const params = new URLSearchParams({
        from: fromId,
        to: toId
    });
    return `${window.location.origin}${window.location.pathname}?${params.toString()}`;
}

function decodeRouteFromURL() {
    const params = new URLSearchParams(window.location.search);
    const from = params.get('from');
    const to = params.get('to');

    if (from && to) {
        return { from, to };
    }
    return null;
}

// Check URL parameters on load
window.addEventListener('load', () => {
    const routeParams = decodeRouteFromURL();
    if (routeParams) {
        // Wait for stations to load, then set selections
        const checkStations = setInterval(() => {
            if (app.stations.length > 0) {
                clearInterval(checkStations);
                document.getElementById('from-station').value = routeParams.from;
                document.getElementById('to-station').value = routeParams.to;
                // Auto-find route
                setTimeout(() => findRoute(), 500);
            }
        }, 100);
    }
});
