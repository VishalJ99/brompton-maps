# Detailed Setup Guide

This guide provides step-by-step instructions for setting up Brompton Maps locally.

## System Requirements

- **Python**: 3.10 or higher
- **Git**: Latest version with Git LFS support
- **Memory**: At least 2GB RAM (for graph processing)
- **Disk Space**: ~500MB for code and graph data

## Step 1: Prerequisites

### Install Git LFS
```bash
# On macOS with Homebrew
brew install git-lfs

# On Ubuntu/Debian
curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | sudo bash
sudo apt-get install git-lfs

# On Windows (download from GitHub)
# https://git-lfs.github.io/

# Initialize Git LFS
git lfs install
```

### Get API Keys

#### Google Maps API Key (Required)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the "Directions API"
4. Create credentials → API Key
5. Restrict the key to "Directions API" for security

#### Mapbox Access Token (Required)
1. Sign up at [Mapbox](https://www.mapbox.com/)
2. Go to [Access Tokens](https://account.mapbox.com/access-tokens/)
3. Create a new token with default scopes

## Step 2: Installation

### Clone Repository
```bash
git lfs install
git clone https://github.com/your-username/bromptonMaps.git
cd bromptonMaps
```

### Set Up Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env file and add your Google Maps API key
# Use your preferred text editor:
nano .env
# or
code .env
```

## Step 3: Verify Setup

### Check Graph Files
```bash
# Check if large graph files downloaded via Git LFS
ls -lah *.json

# You should see files like:
# - bike_graph.json (~11MB)
# - merged_graph.json (~13MB)
# - tfl_stations.json (~3KB)
```

### Test API Server
```bash
# Start the server
python app.py

# In another terminal, test the API
curl http://localhost:5000/api/health
curl http://localhost:5000/api/graph/status
```

Expected output:
```json
{"status": "ok", "graphs_loaded": true}
```

## Step 4: Frontend Setup

### Configure Mapbox
```bash
cd frontend
cp js/config.js.example js/config.js

# Edit config.js and add your Mapbox token
# Replace 'YOUR_MAPBOX_ACCESS_TOKEN_HERE' with your actual token
```

### Start Frontend Server
```bash
# Option 1: Python built-in server
python -m http.server 8080

# Option 2: Node.js http-server (if you have Node.js)
npx http-server -p 8080

# Option 3: VS Code Live Server extension
```

### Test Frontend
1. Open http://localhost:8080 in your browser
2. You should see a map of London with tube stations
3. Try searching for routes between stations

## Step 5: Verification

### Quick Test Route
1. Go to the "Coordinates" tab
2. Click on the map to set start point (e.g., central London)
3. Click again to set end point
4. Click "Find Route"
5. You should see a multi-modal route with bike and tube segments

### API Test
```bash
# Test coordinate routing
curl -X POST http://localhost:5000/api/route/coordinates \
  -H "Content-Type: application/json" \
  -d '{
    "start_lat": 51.5074,
    "start_lon": -0.1278,
    "end_lat": 51.4994,
    "end_lon": -0.1270,
    "max_bike_minutes": 45.0
  }'
```

## Troubleshooting

### Graph Files Not Loading
```bash
# Check Git LFS status
git lfs ls-files

# If files are not downloaded, try:
git lfs pull
```

### API Server Fails to Start
```bash
# Check Python version
python --version  # Should be 3.10+

# Check dependencies
pip list | grep -E "(flask|networkx|requests)"

# Rebuild graphs if needed
python src/fetch_tfl_stations.py
python src/build_tfl_graph.py
```

### Frontend Map Not Loading
1. Check browser console for errors
2. Verify Mapbox token in `frontend/js/config.js`
3. Ensure API server is running on port 5000
4. Check CORS settings in browser

### Memory Issues
```bash
# If graph building runs out of memory, try:
export PYTHONHASHSEED=0  # Consistent memory usage
python src/build_multilayer_bike_graph.py
```

## Development Setup

### Install Development Tools
```bash
pip install ruff pytest
```

### Run Tests
```bash
cd tests
python -m pytest -v
```

### Code Formatting
```bash
# Check code style
ruff check .

# Format code
ruff format .
```

## Production Deployment

For production deployment, consider:

1. **Use a proper WSGI server**: Gunicorn, uWSGI
2. **Set up reverse proxy**: Nginx, Apache
3. **Environment variables**: Secure API key storage
4. **Database**: Consider PostgreSQL for station data
5. **Caching**: Redis for route caching
6. **Monitoring**: Application performance monitoring

Example production startup:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Getting Help

If you encounter issues:

1. Check the [main README](README.md) for basic troubleshooting
2. Look at existing [GitHub issues](../../issues)
3. Create a new issue with:
   - Your operating system and Python version
   - Error messages and logs
   - Steps to reproduce the problem
