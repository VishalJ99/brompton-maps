# Tests

This directory contains unit tests and integration tests for the Brompton Maps project.

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python test_tfl_stations.py
```

## Test Files

- `test_*.py` - Various test modules for different components
- Tests cover TfL station data, routing algorithms, API endpoints, and travel time calculations

## Test Dependencies

Make sure you have the required test dependencies installed:
```bash
pip install -r requirements.txt
```
