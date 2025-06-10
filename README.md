# 🚴‍♂️ Brompton Maps

**Multi-modal routing for London combining cycling and public transport**

Brompton Maps finds optimal bike+transit routes that traditional mapping services miss. Perfect for folding bike users who can cycle to stations, take the tube, and cycle to their final destination.

## 🎯 Problem Solved

Traditional mapping services assume you either:
- Walk + take public transport, OR
- Cycle the entire journey

They miss the optimal combination of cycling to nearby stations, using the tube network efficiently, and cycling the final stretch.

**Example Route**: Shaftesbury Avenue → Imperial College
- 🚴 Cycle ~5min to Preston Road station
- 🚇 Metropolitan line to Baker Street
- 🚴 Cycle ~15min to Imperial College
- ⏱️ **Total: ~35-40 minutes** vs Google Maps 75 minutes

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Git with Git LFS (see installation below)
- Google Maps API key (for bike routing)
- Mapbox access token (for map visualization)

### Installation

1. **Install Git LFS** (if not already installed)
   ```bash
   # macOS
   brew install git-lfs
   
   # Ubuntu/Debian
   sudo apt install git-lfs
   
   # Windows (download from https://git-lfs.github.io/)
   # Or use: winget install GitHub.GitLFS
   
   # Enable Git LFS
   git lfs install
   ```

2. **Clone the repository**
   ```bash
   git clone git@github.com:VishalJ99/bromptonMaps.git
   cd bromptonMaps
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up API keys**
   
   You need two API keys:
   
   **A) Google Maps API Key** (for address search & transit comparison)
   - Get it from: [Google Cloud Console](https://console.cloud.google.com/)
   - Enable APIs: Places API, Directions API, Maps JavaScript API
   - For the backend, set environment variable:
   ```bash
   export GOOGLE_MAPS_API_KEY="your_google_maps_api_key_here"
   # OR create a .env file in project root with:
   # GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
   ```
   
   **B) Mapbox Access Token** (for map visualization)
   - Get it from: [Mapbox Account](https://account.mapbox.com/access-tokens/)
   - Set environment variable for automatic frontend config generation:
   ```bash
   export MAPBOX_ACCESS_TOKEN="pk.your_mapbox_token_here"
   # OR add to your .env file:
   # MAPBOX_ACCESS_TOKEN=pk.your_mapbox_token_here
   ```
   
   Note: The app will automatically generate `frontend/js/config.js` from the template using your environment variables.

5. **Build the routing graphs** (optional - pre-built graphs included via Git LFS)
   ```bash
   # Only needed if you want to rebuild from scratch:

   # Fetch TfL station data
   python src/fetch_tfl_stations.py

   # Build tube network graph
   python src/build_tfl_graph.py

   # Build multi-layer graph with line changes
   python src/build_multilayer_tfl_graph.py

   # Build bike routing graph
   python src/build_multilayer_bike_graph.py

   # Merge graphs for multi-modal routing
   python src/merge_multilayer_graphs.py
   ```

6. **Start the API server**
   ```bash
   python app.py
   ```

7. **Start the frontend**
   ```bash
   cd frontend
   # Serve the frontend (choose one):
   python -m http.server 8080
   # OR: npx http-server -p 8080
   ```

8. **Open in browser**
   ```
   http://localhost:8080
   ```

## 🗺️ Features

### Current Capabilities
- **Address-Based Routing**: Search for addresses using Google Places Autocomplete or click on map
- **Multi-Modal Routes**: Combines cycling and tube travel optimally
- **Interactive Visualization**:
  - Tube routes shown with official TfL line colors
  - Bike routes with dashed green lines using real road geometry
  - Station markers and route waypoints
- **Intelligent Route Selection**:
  - Considers line change penalties (5 minutes each)
  - Customizable station access times via Advanced Settings
  - Configurable cycling speed and distance preferences
- **Advanced Settings**:
  - Adjustable station access time (default 2 minutes)
  - Adjustable train waiting time (default 5 minutes)
  - Clear indication of cycling speed assumptions (~15 km/h)
- **Transit Comparison**: Shows fastest public transport time for comparison

### Route Types
1. **Direct Bike**: For short distances (< 45 minutes cycling)
2. **Bike → Tube**: Cycle to nearest station, take tube to destination area
3. **Tube → Bike**: Take tube to destination area, cycle final distance
4. **Bike → Tube → Bike**: Full multi-modal with both ends cycling

## 🏗️ Architecture

### Backend Components
- **Flask API Server** (`app.py`): REST endpoints for routing and station data
- **Multi-Layer Router** (`src/route_planner_multilayer.py`): Core routing engine with Dijkstra's algorithm
- **Bike Routing Integration** (`src/bike_routing.py`): Pluggable providers (OSRM, Google Maps)
- **Graph Building Pipeline** (`src/build_*.py`): TfL data processing and graph construction
- **NetworkX Graphs**: Efficient pathfinding with proper line change modeling

### Frontend Components
- **Mapbox GL JS**: Interactive map rendering
- **Vanilla JavaScript**: No framework dependencies
- **Responsive Design**: Works on desktop and mobile
- **Real-time Routing**: Live API integration with loading states

### Data Sources
- **Transport for London (TfL)**: Station locations, connections, and line information
- **Google Maps Directions API**: Real bike route geometry and timing
- **OSRM**: Alternative bike routing (configurable)

## 📡 API Reference

### Endpoints

#### `GET /api/stations`
Get all London Underground stations with coordinates and line information.

#### `POST /api/route/coordinates`
Calculate multi-modal route between coordinates.
```json
{
  "start_lat": 51.5074,
  "start_lon": -0.1278,
  "end_lat": 51.4994,
  "end_lon": -0.1270,
  "max_bike_minutes": 45.0,
  "station_access_time": 2.0,  // optional, default 2.0
  "train_waiting_time": 5.0    // optional, default 5.0
}
```

#### `GET /api/graph/status`
Check status of loaded routing graphs.

### Response Format
```json
{
  "status": "success",
  "route": {
    "segments": [
      {
        "type": "bike",
        "from_name": "Start Location",
        "to_name": "Baker Street Station",
        "duration_minutes": 8.5,
        "distance_km": 2.1,
        "geometry": [[lon,lat], [lon,lat], ...]
      },
      {
        "type": "tube",
        "line": "metropolitan",
        "from_name": "Baker Street",
        "to_name": "King's Cross",
        "duration_minutes": 12.0
      }
    ],
    "total_duration": 25.5,
    "is_direct_bike": false
  }
}
```

## 🛠️ Configuration

### Environment Variables
```bash
# Required for bike routing
GOOGLE_MAPS_API_KEY=your_api_key_here

# Optional: Custom OSRM server
OSRM_BASE_URL=http://router.project-osrm.org
```

### Routing Parameters
Edit `src/routing_config.py` to adjust:
- Cycling speed (default: 15 km/h)
- Maximum bike distance (default: 45 minutes)
- Station access buffers
- Line change penalties

### Frontend Configuration
The frontend configuration is automatically generated from environment variables. The app creates `frontend/js/config.js` from the template using:
- `MAPBOX_ACCESS_TOKEN` environment variable
- `GOOGLE_MAPS_API_KEY` environment variable

No manual editing of config files is required.

## 🧪 Development

### Running Tests
```bash
cd tests
python -m pytest
```

### Debug Scripts
```bash
python dev/debug_bike_api.py  # Test bike routing API
python dev/debug_journey.py  # Analyze specific routes
```

### Code Quality
```bash
ruff check .     # Lint code
ruff format .    # Format code
```

## 📁 Project Structure

```
bromptonMaps/
├── README.md                           # This file
├── requirements.txt                    # Python dependencies
├── .env.example                       # Environment template
├── app.py                             # Flask API server (main entry point)
├── src/                               # Application source code
│   ├── route_planner_multilayer.py    # Core routing engine
│   ├── bike_routing.py                # Bike routing integration
│   ├── build_*.py                     # Graph building scripts
│   ├── merge_*.py                     # Graph merging utilities
│   ├── tfl_utils.py                   # TfL data utilities
│   ├── routing_utils.py               # Routing helpers
│   └── routing_config.py              # Configuration
├── data/                              # Graph data and station information
│   ├── tfl_stations.json              # Station data
│   ├── bike_graph.json                # Bike routing graph (LFS)
│   ├── merged_graph.json              # Combined graph (LFS)
│   └── *.pickle files                 # Binary graph caches
├── frontend/                          # Web interface
│   ├── index.html
│   ├── css/styles.css
│   └── js/                           # JavaScript modules
├── tests/                            # Unit tests
└── dev/                              # Development utilities
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`python -m pytest tests/`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Guidelines
- Follow the existing code style (use `ruff` for formatting)
- Add tests for new functionality
- Update documentation for API changes
- Use descriptive commit messages

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Transport for London** for providing comprehensive public transport data
- **OpenStreetMap** and **OSRM** for open-source routing
- **Google Maps Platform** for accurate cycling directions
- **Mapbox** for beautiful map visualization
- **NetworkX** for graph algorithms

## 📞 Support

- Create an [issue](../../issues) for bug reports or feature requests
- Check existing [discussions](../../discussions) for Q&A
- See [API documentation](docs/API.md) for detailed endpoint information

---

**Made with ❤️ for London cyclists and public transport users**
