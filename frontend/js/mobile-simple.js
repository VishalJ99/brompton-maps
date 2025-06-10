// ABOUTME: Simple mobile header handler for MVP - minimal UI with basic functionality
// ABOUTME: Handles from/to inputs and route finding without fancy features

document.addEventListener('DOMContentLoaded', function() {
    // Check if mobile
    const isMobile = window.innerWidth <= 768 || /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    if (!isMobile) return;
    
    // Get elements
    const fromInput = document.getElementById('mobile-from');
    const toInput = document.getElementById('mobile-to');
    const goButton = document.getElementById('mobile-go');
    
    if (!fromInput || !toInput || !goButton) return;
    
    // Store selected coordinates from autocomplete
    let selectedCoords = { from: null, to: null };
    
    // Initialize Google Places Autocomplete
    setTimeout(() => {
        if (window.google && window.google.maps && window.google.maps.places) {
            const autocompleteOptions = {
                bounds: { north: 51.7, south: 51.2, east: 0.3, west: -0.6 },
                componentRestrictions: { country: 'gb' },
                fields: ['geometry', 'name', 'formatted_address']
            };
            
            const fromAutocomplete = new google.maps.places.Autocomplete(fromInput, autocompleteOptions);
            const toAutocomplete = new google.maps.places.Autocomplete(toInput, autocompleteOptions);
            
            // Store coordinates when place is selected
            fromAutocomplete.addListener('place_changed', () => {
                const place = fromAutocomplete.getPlace();
                if (place.geometry && place.geometry.location) {
                    selectedCoords.from = {
                        lat: place.geometry.location.lat(),
                        lon: place.geometry.location.lng()
                    };
                }
            });
            
            toAutocomplete.addListener('place_changed', () => {
                const place = toAutocomplete.getPlace();
                if (place.geometry && place.geometry.location) {
                    selectedCoords.to = {
                        lat: place.geometry.location.lat(),
                        lon: place.geometry.location.lng()
                    };
                }
            });
            
            // Clear coords when user types (not selecting from dropdown)
            fromInput.addEventListener('input', () => {
                selectedCoords.from = null;
            });
            
            toInput.addEventListener('input', () => {
                selectedCoords.to = null;
            });
        }
    }, 1000); // Wait for Google Maps API to load
    
    // Handle go button click
    goButton.addEventListener('click', async function() {
        const fromValue = fromInput.value.trim();
        const toValue = toInput.value.trim();
        
        if (!fromValue || !toValue) {
            alert('Please enter both locations');
            return;
        }
        
        // Show loading
        goButton.textContent = 'Finding...';
        goButton.disabled = true;
        
        try {
            // Use autocomplete coords if available, otherwise show error
            const fromCoords = selectedCoords.from;
            const toCoords = selectedCoords.to;
            
            if (!fromCoords || !toCoords) {
                alert('Please select locations from the dropdown suggestions');
                return;
            }
            
            // Make direct API call
            const loadingOverlay = document.getElementById('loading-overlay');
            if (loadingOverlay) loadingOverlay.classList.add('active');
            
            const response = await fetch('/api/route/coordinates', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    start_lat: fromCoords.lat,
                    start_lon: fromCoords.lon,
                    end_lat: toCoords.lat,
                    end_lon: toCoords.lon,
                    max_bike_minutes: 45.0,
                    station_access_time: 2.0,
                    train_waiting_time: 5.0,
                    line_change_time: 5.0
                }),
            });
            
            const result = await response.json();
            
            if (result.status === 'success' && result.route) {
                // Store route in app state
                if (window.app) {
                    window.app.currentRoute = result.route;
                }
                
                // Display route on mobile
                displayMobileRoute(result.route);
                
                // Visualize on map
                if (window.visualizeMultiModalRoute) {
                    try {
                        window.visualizeMultiModalRoute(result.route);
                    } catch (err) {
                        console.error('Map visualization error:', err);
                    }
                }
            } else {
                // Show error in results div
                const resultsDiv = document.getElementById('mobile-results');
                const contentDiv = document.getElementById('mobile-results-content');
                if (resultsDiv && contentDiv) {
                    contentDiv.innerHTML = '<div style="color: #d32f2f; font-size: 16px;">No route found. Please try different locations.</div>';
                    resultsDiv.style.display = 'block';
                }
            }
            
            if (loadingOverlay) loadingOverlay.classList.remove('active');
        } catch (error) {
            console.error('Error:', error);
            alert('Error finding route. Please try again.');
        } finally {
            goButton.textContent = 'Go';
            goButton.disabled = false;
        }
    });
    
    
    // Display route results on mobile
    function displayMobileRoute(route) {
        const resultsDiv = document.getElementById('mobile-results');
        const contentDiv = document.getElementById('mobile-results-content');
        
        if (!resultsDiv || !contentDiv) return;
        
        // Build HTML for route display
        let html = '<h3 style="margin: 0 0 12px 0; font-size: 18px;">Journey Summary</h3>';
        html += `<div style="font-size: 24px; font-weight: bold; color: #003688; margin-bottom: 16px;">${Math.round(route.total_duration_minutes || route.total_duration)} min</div>`;
        
        // Show segments
        html += '<div style="border-top: 1px solid #eee; padding-top: 12px;">';
        
        route.segments.forEach((segment, index) => {
            const icon = segment.mode === 'bike' ? '🚴' : '🚇';
            const duration = Math.round(segment.duration_minutes || segment.duration);
            
            html += `<div style="margin-bottom: 12px; padding: 8px; background: #f5f5f5; border-radius: 4px;">`;
            html += `<div style="font-size: 16px; margin-bottom: 4px;">${icon} ${segment.mode === 'bike' ? 'Bike' : segment.line || 'Tube'} - ${duration} min</div>`;
            
            if (segment.from_name && segment.to_name) {
                html += `<div style="font-size: 14px; color: #666;">`;
                html += `${segment.from_name} → ${segment.to_name}`;
                html += `</div>`;
            }
            
            html += `</div>`;
        });
        
        html += '</div>';
        
        contentDiv.innerHTML = html;
        resultsDiv.style.display = 'block';
    }

});