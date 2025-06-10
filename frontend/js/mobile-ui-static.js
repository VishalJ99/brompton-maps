// ABOUTME: Simple static mobile UI handler for reliable mobile interface
// ABOUTME: Handles basic interactions for the static HTML mobile UI elements

// Simple static mobile UI handler
document.addEventListener('DOMContentLoaded', function() {
    console.log('Static mobile UI handler loaded');
    
    // Check if we should show mobile UI
    const isMobile = window.innerWidth <= 768 || 
                     /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    
    console.log('Mobile check:', { 
        innerWidth: window.innerWidth, 
        userAgent: navigator.userAgent,
        isMobile: isMobile 
    });
    
    if (!isMobile) {
        console.log('Not mobile, skipping static mobile UI');
        return;
    }
    
    // Get elements
    const searchBox = document.querySelector('.mobile-search-box-static');
    const inputPanel = document.querySelector('.mobile-input-panel-static');
    const backdrop = document.querySelector('.mobile-backdrop-static');
    const closeBtn = document.querySelector('.mobile-close-static');
    const findRouteBtn = document.getElementById('mobile-find-route-static');
    const fromInput = document.getElementById('mobile-from-static');
    const toInput = document.getElementById('mobile-to-static');
    
    console.log('Elements found:', {
        searchBox: !!searchBox,
        inputPanel: !!inputPanel,
        backdrop: !!backdrop,
        closeBtn: !!closeBtn,
        findRouteBtn: !!findRouteBtn
    });
    
    // Show input panel when search box clicked
    if (searchBox) {
        searchBox.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Search box clicked');
            if (inputPanel) inputPanel.style.display = 'block';
            if (backdrop) backdrop.style.display = 'block';
        });
    }
    
    // Hide input panel
    function hidePanel() {
        console.log('Hiding panel');
        if (inputPanel) inputPanel.style.display = 'none';
        if (backdrop) backdrop.style.display = 'none';
    }
    
    if (closeBtn) {
        closeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            hidePanel();
        });
    }
    
    if (backdrop) {
        backdrop.addEventListener('click', function(e) {
            e.preventDefault();
            hidePanel();
        });
    }
    
    // Handle route finding
    if (findRouteBtn) {
        findRouteBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            console.log('Find route clicked');
            
            // Get values
            const fromValue = fromInput ? fromInput.value : '';
            const toValue = toInput ? toInput.value : '';
            
            console.log('Route values:', { from: fromValue, to: toValue });
            
            if (!fromValue || !toValue) {
                alert('Please enter both start and end locations');
                return;
            }
            
            // Copy values to main inputs if they exist
            const mainFromInput = document.getElementById('from-address');
            const mainToInput = document.getElementById('to-address');
            
            if (mainFromInput) mainFromInput.value = fromValue;
            if (mainToInput) mainToInput.value = toValue;
            
            // Hide panel
            hidePanel();
            
            // Show loading
            const loadingOverlay = document.getElementById('loading-overlay');
            if (loadingOverlay) loadingOverlay.classList.add('active');
            
            // Use existing route finding or make direct API call
            if (typeof findRouteCoordinates === 'function') {
                console.log('Using existing findRouteCoordinates');
                findRouteCoordinates();
            } else {
                console.log('Making direct API call');
                // Direct API call as fallback
                try {
                    const response = await fetch('/api/route', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            from_address: fromValue,
                            to_address: toValue
                        })
                    });
                    
                    const result = await response.json();
                    console.log('Route result:', result);
                    
                    if (result.status === 'success') {
                        alert(`Route found: ${Math.round(result.route.total_duration_minutes)} minutes`);
                    } else {
                        alert('Route not found');
                    }
                } catch (error) {
                    console.error('Route error:', error);
                    alert('Error finding route');
                } finally {
                    if (loadingOverlay) loadingOverlay.classList.remove('active');
                }
            }
        });
    }
    
    // Add some basic styling to ensure visibility
    if (searchBox) {
        searchBox.style.display = 'block';
        searchBox.style.visibility = 'visible';
    }
});