# Brompton Maps Frontend

Interactive map-based visualization for London tube routing (with future bike+tube support).

## Setup

1. **Get a Mapbox Access Token**
   - Sign up at https://www.mapbox.com/
   - Go to https://account.mapbox.com/access-tokens/
   - Create a new access token
   - Copy `js/config.js.example` to `js/config.js` and add your token

2. **Start the Backend API Server**
   ```bash
   cd ..
   python api_server.py
   ```
   The API server will run on http://localhost:5000

3. **Serve the Frontend**

   Option 1 - Python simple server:
   ```bash
   python -m http.server 8080
   ```

   Option 2 - Node.js http-server:
   ```bash
   npx http-server -p 8080
   ```

   Option 3 - VS Code Live Server extension

4. **Open in Browser**
   Navigate to http://localhost:8080/frontend/

## Features

### Current (Phase 1 - Tube Only)
- Interactive map showing all London Underground stations
- Station-to-station routing using tube network
- Color-coded tube lines
- Journey time calculations
- Detailed journey breakdown
- Route visualization on map

### Planned (Phase 2 - Bike Integration)
- Point-to-point routing (any coordinates)
- Multi-modal journeys (bike + tube)
- Bike route visualization with dashed lines
- Buffer time visualization
- Route comparison

### Future (Phase 3)
- Alternative route suggestions
- Time-of-day routing
- Route saving and sharing
- Journey statistics
- Export routes as images

## Architecture

- **Mapbox GL JS**: Map rendering and interaction
- **Flask API**: Backend routing calculations
- **NetworkX**: Graph-based routing algorithms
- **Vanilla JavaScript**: No frontend framework dependencies

## API Endpoints

- `GET /api/stations` - Get all tube stations
- `POST /api/route/station-to-station` - Calculate tube-only route
- `GET /api/graph/status` - Check graph availability
- `POST /api/route/point-to-point` - (Future) Multi-modal routing

## Customization

### Styling
Edit `css/styles.css` to customize the appearance.

### Map Style
Change the Mapbox style in `js/map.js`:
```javascript
style: 'mapbox://styles/mapbox/light-v11', // Options: streets-v12, dark-v11, satellite-v9
```

### API URL
Update the API URL in `js/app.js` if running on a different host:
```javascript
apiUrl: 'http://localhost:5000/api',
```
