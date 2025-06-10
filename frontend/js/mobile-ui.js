// ABOUTME: Google Maps-style floating card UI for mobile devices
// ABOUTME: Manages search box, input cards, route summary, and detailed view states

class MobileUI {
    constructor() {
        this.currentState = 'search'; // search, input, summary, details
        this.elements = {};
        this.route = null;
        this.touchStartY = 0;
        this.summaryCardY = 0;
        
        // Bind methods
        this.handleSearchClick = this.handleSearchClick.bind(this);
        this.handleBackdropClick = this.handleBackdropClick.bind(this);
        this.handleFindRoute = this.handleFindRoute.bind(this);
        this.handleSummarySwipe = this.handleSummarySwipe.bind(this);
        this.handleDetailsClose = this.handleDetailsClose.bind(this);
    }
    
    initialize() {
        this.createMobileElements();
        this.attachEventListeners();
        this.setState('search');
        
        // Add initialization indicator
        document.body.setAttribute('data-mobile-ui-initialized', 'true');
    }
    
    createMobileElements() {
        // Create mobile container
        const mobileContainer = document.createElement('div');
        mobileContainer.className = 'mobile-ui-container';
        
        // Search box (always visible)
        const searchBox = document.createElement('div');
        searchBox.className = 'mobile-search-box';
        searchBox.innerHTML = `
            <div class="search-box-content">
                <span class="search-icon">🔍</span>
                <span class="search-placeholder">Where to?</span>
            </div>
        `;
        
        // Input card (expanded search)
        const inputCard = document.createElement('div');
        inputCard.className = 'mobile-input-card';
        inputCard.innerHTML = `
            <div class="input-card-content">
                <div class="input-group">
                    <label>From</label>
                    <div class="input-wrapper">
                        <input type="text" id="mobile-from-address" class="mobile-address-input" placeholder="Current location or search...">
                        <button class="current-location-btn" title="Use current location">📍</button>
                    </div>
                </div>
                <div class="input-group">
                    <label>To</label>
                    <input type="text" id="mobile-to-address" class="mobile-address-input" placeholder="Search for destination...">
                </div>
                <button class="mobile-find-route-btn">
                    <span class="btn-text">Find Route</span>
                    <span class="btn-spinner" style="display: none;">⏳</span>
                </button>
                <button class="settings-btn" title="Advanced settings">⚙️</button>
            </div>
        `;
        
        // Route summary card
        const summaryCard = document.createElement('div');
        summaryCard.className = 'mobile-route-summary';
        summaryCard.innerHTML = `
            <div class="summary-handle"></div>
            <div class="summary-content">
                <div class="route-endpoints">
                    <div class="route-from">From: <span class="from-text"></span></div>
                    <div class="route-to">To: <span class="to-text"></span></div>
                </div>
                <div class="route-time">
                    <div class="total-time">--</div>
                    <div class="comparison-time">-- without bike</div>
                </div>
                <div class="swipe-indicator">Swipe up for details</div>
            </div>
        `;
        
        // Detailed route view
        const detailsView = document.createElement('div');
        detailsView.className = 'mobile-route-details';
        detailsView.innerHTML = `
            <div class="details-header">
                <button class="details-close-btn">✕</button>
                <h3>Route Details</h3>
            </div>
            <div class="details-content">
                <!-- Route details will be inserted here -->
            </div>
        `;
        
        // Backdrop
        const backdrop = document.createElement('div');
        backdrop.className = 'mobile-backdrop';
        
        // Settings modal
        const settingsModal = document.createElement('div');
        settingsModal.className = 'mobile-settings-modal';
        settingsModal.innerHTML = `
            <div class="settings-modal-content">
                <div class="settings-header">
                    <h3>Advanced Settings</h3>
                    <button class="settings-close-btn">✕</button>
                </div>
                <div class="settings-body">
                    <div class="setting-group">
                        <label for="mobile-station-access-time">Station Access Time (min)</label>
                        <input type="number" id="mobile-station-access-time" value="2" min="0" step="0.5">
                    </div>
                    <div class="setting-group">
                        <label for="mobile-train-waiting-time">Train Waiting Time (min)</label>
                        <input type="number" id="mobile-train-waiting-time" value="5" min="0" step="0.5">
                    </div>
                    <div class="setting-group">
                        <label for="mobile-line-change-time">Line Change Time (min)</label>
                        <input type="number" id="mobile-line-change-time" value="5" min="0" step="0.5">
                    </div>
                </div>
            </div>
        `;
        
        // Add all elements to container
        mobileContainer.appendChild(searchBox);
        mobileContainer.appendChild(backdrop);
        mobileContainer.appendChild(inputCard);
        mobileContainer.appendChild(summaryCard);
        mobileContainer.appendChild(detailsView);
        mobileContainer.appendChild(settingsModal);
        
        // Add to body
        document.body.appendChild(mobileContainer);
        
        // Store references
        this.elements = {
            container: mobileContainer,
            searchBox,
            inputCard,
            summaryCard,
            detailsView,
            backdrop,
            settingsModal,
            fromInput: inputCard.querySelector('#mobile-from-address'),
            toInput: inputCard.querySelector('#mobile-to-address'),
            findRouteBtn: inputCard.querySelector('.mobile-find-route-btn'),
            currentLocationBtn: inputCard.querySelector('.current-location-btn'),
            settingsBtn: inputCard.querySelector('.settings-btn'),
            settingsCloseBtn: settingsModal.querySelector('.settings-close-btn'),
            detailsCloseBtn: detailsView.querySelector('.details-close-btn'),
            summaryContent: summaryCard.querySelector('.summary-content'),
            detailsContent: detailsView.querySelector('.details-content')
        };
    }
    
    attachEventListeners() {
        // Search box click
        this.elements.searchBox.addEventListener('click', this.handleSearchClick);
        
        // Backdrop click
        this.elements.backdrop.addEventListener('click', this.handleBackdropClick);
        
        // Find route button
        this.elements.findRouteBtn.addEventListener('click', this.handleFindRoute);
        
        // Current location button
        this.elements.currentLocationBtn.addEventListener('click', () => {
            this.useCurrentLocation();
        });
        
        // Settings button
        this.elements.settingsBtn.addEventListener('click', () => {
            this.showSettings();
        });
        
        // Settings close
        this.elements.settingsCloseBtn.addEventListener('click', () => {
            this.hideSettings();
        });
        
        // Details close
        this.elements.detailsCloseBtn.addEventListener('click', this.handleDetailsClose);
        
        // Summary card swipe
        this.setupSummarySwipe();
        
        // Sync with main app inputs
        this.syncInputs();
    }
    
    setupSummarySwipe() {
        const summary = this.elements.summaryCard;
        let startY = 0;
        let currentY = 0;
        let isDragging = false;
        
        summary.addEventListener('touchstart', (e) => {
            startY = e.touches[0].clientY;
            isDragging = true;
            summary.style.transition = 'none';
        });
        
        summary.addEventListener('touchmove', (e) => {
            if (!isDragging) return;
            currentY = e.touches[0].clientY;
            const deltaY = currentY - startY;
            if (deltaY < 0) { // Only allow upward swipe
                summary.style.transform = `translateY(${deltaY}px)`;
            }
        });
        
        summary.addEventListener('touchend', (e) => {
            isDragging = false;
            summary.style.transition = 'transform 0.3s ease';
            const deltaY = currentY - startY;
            
            if (deltaY < -50) { // Threshold for showing details
                this.setState('details');
            }
            summary.style.transform = '';
        });
    }
    
    syncInputs() {
        // Sync mobile inputs with main app
        this.elements.fromInput.addEventListener('input', (e) => {
            const mainFromInput = document.getElementById('from-address');
            if (mainFromInput) mainFromInput.value = e.target.value;
        });
        
        this.elements.toInput.addEventListener('input', (e) => {
            const mainToInput = document.getElementById('to-address');
            if (mainToInput) mainToInput.value = e.target.value;
        });
        
        // Initialize Google Places autocomplete
        if (window.google && window.google.maps && window.google.maps.places) {
            this.initializeAutocomplete();
        } else {
            // Wait for Google Maps to load
            const checkGoogle = setInterval(() => {
                if (window.google && window.google.maps && window.google.maps.places) {
                    clearInterval(checkGoogle);
                    this.initializeAutocomplete();
                }
            }, 100);
        }
    }
    
    initializeAutocomplete() {
        // Set up Google Places autocomplete for mobile inputs
        const options = {
            componentRestrictions: { country: 'gb' },
            bounds: new google.maps.LatLngBounds(
                new google.maps.LatLng(51.2868, -0.5106),
                new google.maps.LatLng(51.6919, 0.3340)
            ),
            strictBounds: false
        };
        
        const fromAutocomplete = new google.maps.places.Autocomplete(this.elements.fromInput, options);
        const toAutocomplete = new google.maps.places.Autocomplete(this.elements.toInput, options);
        
        fromAutocomplete.addListener('place_changed', () => {
            const place = fromAutocomplete.getPlace();
            if (place.geometry) {
                app.selectedPlaces.from = {
                    name: place.name || place.formatted_address,
                    lat: place.geometry.location.lat(),
                    lng: place.geometry.location.lng()
                };
                document.getElementById('from-lat').value = place.geometry.location.lat();
                document.getElementById('from-lon').value = place.geometry.location.lng();
            }
        });
        
        toAutocomplete.addListener('place_changed', () => {
            const place = toAutocomplete.getPlace();
            if (place.geometry) {
                app.selectedPlaces.to = {
                    name: place.name || place.formatted_address,
                    lat: place.geometry.location.lat(),
                    lng: place.geometry.location.lng()
                };
                document.getElementById('to-lat').value = place.geometry.location.lat();
                document.getElementById('to-lon').value = place.geometry.location.lng();
            }
        });
    }
    
    setState(state) {
        this.currentState = state;
        
        // Remove all state classes
        this.elements.container.className = 'mobile-ui-container';
        this.elements.container.classList.add(`state-${state}`);
        
        // Handle backdrop
        if (state === 'input' || state === 'settings') {
            this.elements.backdrop.classList.add('visible');
        } else {
            this.elements.backdrop.classList.remove('visible');
        }
        
        // Handle specific states
        switch(state) {
            case 'search':
                this.elements.inputCard.classList.remove('visible');
                this.elements.summaryCard.classList.remove('visible');
                this.elements.detailsView.classList.remove('visible');
                break;
                
            case 'input':
                this.elements.inputCard.classList.add('visible');
                this.elements.summaryCard.classList.remove('visible');
                this.elements.detailsView.classList.remove('visible');
                this.elements.fromInput.focus();
                break;
                
            case 'summary':
                this.elements.inputCard.classList.remove('visible');
                this.elements.summaryCard.classList.add('visible');
                this.elements.detailsView.classList.remove('visible');
                break;
                
            case 'details':
                this.elements.detailsView.classList.add('visible');
                break;
        }
    }
    
    handleSearchClick() {
        if (this.currentState === 'search') {
            this.setState('input');
        }
    }
    
    handleBackdropClick() {
        if (this.currentState === 'input') {
            this.setState('search');
        } else if (this.elements.settingsModal.classList.contains('visible')) {
            this.hideSettings();
        }
    }
    
    async handleFindRoute() {
        // Show loading state
        this.elements.findRouteBtn.classList.add('loading');
        this.elements.findRouteBtn.querySelector('.btn-text').style.display = 'none';
        this.elements.findRouteBtn.querySelector('.btn-spinner').style.display = 'inline';
        
        try {
            // Trigger main app's route finding
            if (window.findRouteCoordinates) {
                await window.findRouteCoordinates();
            }
        } finally {
            // Reset button state
            this.elements.findRouteBtn.classList.remove('loading');
            this.elements.findRouteBtn.querySelector('.btn-text').style.display = 'inline';
            this.elements.findRouteBtn.querySelector('.btn-spinner').style.display = 'none';
        }
    }
    
    handleDetailsClose() {
        this.setState('summary');
    }
    
    useCurrentLocation() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const lat = position.coords.latitude;
                    const lng = position.coords.longitude;
                    
                    // Update inputs
                    this.elements.fromInput.value = 'Current location';
                    document.getElementById('from-lat').value = lat;
                    document.getElementById('from-lon').value = lng;
                    document.getElementById('from-address').value = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
                    
                    app.selectedPlaces.from = {
                        name: 'Current location',
                        lat: lat,
                        lng: lng
                    };
                    
                    // Update map marker
                    if (window.updateCoordinateMarker) {
                        window.updateCoordinateMarker('start', [lng, lat]);
                    }
                },
                (error) => {
                    alert('Unable to get current location. Please enter manually.');
                }
            );
        }
    }
    
    showSettings() {
        this.elements.settingsModal.classList.add('visible');
        this.elements.backdrop.classList.add('visible');
        
        // Sync settings values
        document.getElementById('mobile-station-access-time').value = app.settings.stationAccessTime;
        document.getElementById('mobile-train-waiting-time').value = app.settings.trainWaitingTime;
        document.getElementById('mobile-line-change-time').value = app.settings.lineChangeTime;
    }
    
    hideSettings() {
        this.elements.settingsModal.classList.remove('visible');
        if (this.currentState !== 'input') {
            this.elements.backdrop.classList.remove('visible');
        }
        
        // Apply settings
        app.settings.stationAccessTime = parseFloat(document.getElementById('mobile-station-access-time').value);
        app.settings.trainWaitingTime = parseFloat(document.getElementById('mobile-train-waiting-time').value);
        app.settings.lineChangeTime = parseFloat(document.getElementById('mobile-line-change-time').value);
    }
    
    showRouteSummary(route) {
        this.route = route;
        
        // Update summary content
        const fromText = this.elements.summaryCard.querySelector('.from-text');
        const toText = this.elements.summaryCard.querySelector('.to-text');
        const totalTime = this.elements.summaryCard.querySelector('.total-time');
        const comparisonTime = this.elements.summaryCard.querySelector('.comparison-time');
        
        fromText.textContent = app.selectedPlaces.from?.name || 'Start';
        toText.textContent = app.selectedPlaces.to?.name || 'End';
        
        const totalMinutes = Math.round(route.total_duration_minutes);
        totalTime.textContent = `${totalMinutes} min`;
        
        // Calculate tube-only time
        const tubeOnlyMinutes = route.segments
            .filter(seg => seg.mode === 'tube' || seg.mode === 'line_change')
            .reduce((acc, seg) => acc + seg.duration_minutes, 0);
        
        if (tubeOnlyMinutes > 0) {
            comparisonTime.textContent = `${Math.round(tubeOnlyMinutes)} min without bike`;
        } else {
            comparisonTime.textContent = 'Direct bike route';
        }
        
        // Update details content
        this.updateDetailsContent(route);
        
        // Show summary
        this.setState('summary');
    }
    
    updateDetailsContent(route) {
        const content = this.elements.detailsContent;
        content.innerHTML = ''; // Clear existing
        
        // Copy route display from main app
        const mainRouteResults = document.querySelector('.route-results');
        if (mainRouteResults) {
            content.innerHTML = mainRouteResults.innerHTML;
        }
    }
    
    // Check if device is mobile
    static isMobile() {
        // Primary: Check for iOS devices (Safari on iPhone/iPad)
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
        if (isIOS) return true;
        
        // Secondary: Check for Android
        const isAndroid = /Android/i.test(navigator.userAgent);
        if (isAndroid) return true;
        
        // Tertiary: Check viewport (matches CSS breakpoint)
        if (window.matchMedia && window.matchMedia('(max-width: 768px)').matches) {
            return true;
        }
        
        // Quaternary: Touch capability
        if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
            return true;
        }
        
        // Final: Viewport width
        return window.innerWidth <= 768;
    }
}

// Export for use in other modules
window.MobileUI = MobileUI;