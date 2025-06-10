# Mobile UI Fix Plan

## Current Issues

### 1. Google Maps Autocomplete Not Working on Mobile
- **Problem**: Mobile inputs use Nominatim geocoding instead of Google Places API
- **Cause**: mobile-simple.js was built for MVP without Google integration
- **Impact**: Less accurate address search, no autocomplete suggestions

### 2. Go Button Cut Off on Narrow Screens
- **Problem**: Button is partially cut off on 320px screens (iPhone SE)
- **Cause**: Too much padding and spacing in the flexbox layout
- **Current spacing**: padding: 10px, gap: 8px, input padding: 8px, button padding: 8px 16px
- **Total fixed space**: ~100px out of 320px

## Implementation Plan

### Fix 1: Add Google Places Autocomplete to Mobile

**File**: `frontend/js/mobile-simple.js`

**Add after line 14**:
```javascript
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
```

**Update lines 32-33**:
```javascript
// Use autocomplete coords if available, otherwise geocode
const fromCoords = selectedCoords.from || await geocodeAddress(fromValue);
const toCoords = selectedCoords.to || await geocodeAddress(toValue);
```

### Fix 2: Reduce Spacing for Mobile Header

**File**: `frontend/index.html`

**Update line 185** (mobile header div):
```html
<div class="mobile-header" id="mobile-header" style="display: none; position: fixed; top: 0; left: 0; right: 0; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 6px; z-index: 1000;">
    <div style="display: flex; gap: 4px; align-items: center;">
        <input type="text" id="mobile-from" placeholder="From" style="flex: 1; padding: 6px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; min-width: 0;">
        <input type="text" id="mobile-to" placeholder="To" style="flex: 1; padding: 6px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; min-width: 0;">
        <button id="mobile-go" style="padding: 6px 10px; background: #003688; color: white; border: none; border-radius: 4px; font-size: 14px; font-weight: 600; white-space: nowrap;">Go</button>
    </div>
</div>
```

**Changes**:
- Container padding: 10px → 6px (saves 8px)
- Gap: 8px → 4px (saves 8px)
- Input padding: 8px → 6px (saves 8px)
- Button padding: 8px 16px → 6px 10px (saves 14px)
- Added `min-width: 0` to inputs for proper flex behavior
- Added `white-space: nowrap` to button
- **Total saved**: 38px horizontal space

## Expected Results

1. **Google Autocomplete**: Mobile users will see address suggestions as they type, matching desktop experience
2. **Layout Fix**: All elements will fit properly on 320px screens
3. **Fallback**: If Google API fails, Nominatim geocoding still works
4. **User Experience**: Consistent with desktop, easier address entry

## Testing Plan

1. Test on 320px width device (iPhone SE)
2. Verify autocomplete dropdown appears
3. Check that selected addresses populate coordinates
4. Ensure manual typing still works with Nominatim fallback
5. Confirm route calculation and display still function

## Notes

- Google Maps API is already loaded by app.js
- API key is configured in CONFIG.GOOGLE_MAPS_API_KEY
- This maintains the simple MVP approach while adding key functionality
- No changes needed to backend or map visualization code