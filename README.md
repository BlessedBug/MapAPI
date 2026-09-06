# Fuel Route Optimizer

A web application and API built with Django and Django REST Framework that computes driving routes between locations in the United States and determines the most cost-effective fuel stops along the way.

## Table of Contents

- [Features](#features)
- [Technical Details](#technical-details)
- [Quick Setup](#quick-setup)
- [Usage](#usage)
  - [Web Dashboard](#web-dashboard)
  - [API Endpoint](#api-endpoint)
- [Running Tests](#running-tests)
- [License](#license)

## Features

- **Route Calculation** — Computes distance, driving duration, and route geometry between a starting location and a destination.
- **Fuel Optimization** — Automatically plans refueling stops based on a 500-mile vehicle range constraint and current retail fuel prices.
- **Cost Tracking** — Calculates total fuel consumption at 10 miles per gallon (MPG), along with the estimated monetary cost for each leg of the journey.
- **Interactive Interface** — A built-in dashboard with an interactive map (Leaflet.js) displaying the route path, starting point, destination, and fuel stops.

## Technical Details

| Component  | Technology |
|------------|------------|
| Backend    | Django, Django REST Framework |
| Routing    | Open Source Routing Machine (OSRM) public API, simplified geometry overview for efficient performance |
| Geocoding  | OpenStreetMap Nominatim |
| Database   | SQLite, pre-populated with fuel price records from the project dataset |
| Frontend   | Leaflet.js interactive map |

## Quick Setup

### 1. Clone the repository

```bash
git clone https://github.com/BlessedBug/MapAPI.git
cd MapAPI
```

### 2. Create and activate a virtual environment

```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the development server

```bash
python manage.py runserver 8181
```

## Usage

### Web Dashboard

Open your browser and navigate to `http://127.0.0.1:8181/`. Use the searchable city fields to select or type an origin and destination, then click **Find Route & Fuel Stops** to view the map and cost/distance summary.

### API Endpoint

Send a `POST` request to `http://127.0.0.1:8181/` with a JSON body:

```json
{
  "origin": "Chicago, IL",
  "destination": "Dallas, TX"
}
```

**Example response fields:**

```json
{
  "distance_miles": 0,
  "duration_hours": 0,
  "total_fuel_cost": 0,
  "fuel_stops": [],
  "route_geometry": {}
}
```

> Response shape shown for illustration — see the API views for exact field names and behavior.

## Running Tests

To run the test suite included in the application:

```bash
python manage.py test
```

## License

Specify a license (e.g., MIT) here, or remove this section if the project is not yet licensed.
