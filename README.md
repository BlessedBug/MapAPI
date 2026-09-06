# Fuel Route Optimizer

A Django REST API that plans a fuel-efficient driving route between two
U.S. locations.

The API:

1.  Geocodes the origin and destination with Nominatim.
2.  Requests a driving route and route geometry from OSRM.
3.  Selects fuel stations from the local dataset that fall within a
    configurable corridor around the route.
4.  Projects candidate stations onto the route to determine their
    position in route miles.
5.  Applies a range-constrained greedy fuel-purchasing algorithm.
6.  Returns route information, fuel consumption, estimated fuel cost,
    and recommended fuel stops.

The project also includes a small browser interface for testing the API
and displaying the route with Leaflet.

------------------------------------------------------------------------

## Features

-   Django 6.1 application with Django REST Framework.
-   U.S.-only location validation through Nominatim.
-   Driving routes supplied by OSRM.
-   GeoJSON route geometry for station-to-route matching and map
    display.
-   Fuel station data stored locally in SQLite.
-   Separate physical station and price-observation models.
-   Geographic database prefilter before precise route matching.
-   Haversine distance calculations and route-segment projection.
-   Greedy fuel purchasing under a 500-mile maximum vehicle range.
-   Three cache levels:
    -   Geocoding results: 24 hours.
    -   OSRM routes: 6 hours.
    -   Complete optimization responses: 15 minutes.
-   HTTP retries for transient upstream failures.
-   Explicit timeout handling and HTTP status mapping.
-   Django middleware for CSRF, clickjacking protection, and security
    handling.
-   Automated tests covering API validation, upstream failures, fuel
    calculations, route boundaries, price data, and optimization
    scenarios.

------------------------------------------------------------------------

## Architecture

``` text
Client
  |
  | POST /
  v
Django / Django REST Framework
  |
  +--> Request validation
  |
  +--> Complete-result cache
  |
  +--> Nominatim
  |      |
  |      +--> Origin coordinates
  |      +--> Destination coordinates
  |
  +--> OSRM
  |      |
  |      +--> Driving distance
  |      +--> Duration
  |      +--> Route geometry
  |
  +--> Station service
  |      |
  |      +--> Database corridor filter
  |      +--> Route-segment projection
  |      +--> Ordered station positions
  |
  +--> Fuel optimizer
         |
         +--> Fuel consumption
         +--> Reachability
         +--> Greedy station selection
         +--> Purchase quantities
         +--> Cost calculation
  |
  v
JSON response
```

### Project structure

``` text
krot/
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── routes/
│   ├── management/
│   │   └── commands/
│   │       ├── import_fuel_prices.py
│   │       └── geocode_stations.py
│   ├── migrations/
│   ├── services/
│   │   ├── cost_calculator.py
│   │   ├── fuel_optimizer.py
│   │   ├── routing_service.py
│   │   └── station_service.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── tests/
├── data/
│   └── fuel-prices-for-be-assessment.csv
├── db.sqlite3
├── manage.py
├── requirements.txt
└── README.md
```

------------------------------------------------------------------------

## Requirements

-   Python 3.12 or another Python version supported by the pinned Django
    release.
-   Internet access for Nominatim and OSRM requests.
-   A terminal or shell.
-   Git.

The repository currently uses SQLite for local development. No
PostgreSQL server is required to run the included version.

------------------------------------------------------------------------

## Clone the repository

Replace `<repository-url>` with the URL of your GitHub repository.

``` bash
git clone <repository-url>
cd MapAPI
```

If the GitHub repository uses a different directory name, enter that
directory instead.

------------------------------------------------------------------------

## Create a virtual environment

### Windows

``` powershell
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

Upgrade pip:

``` bash
python -m pip install --upgrade pip
```

Install the project dependencies:

``` bash
pip install -r requirements.txt
```

------------------------------------------------------------------------

## Environment configuration

Create a `.env` file in the project root.

Example:

``` env
SECRET_KEY=replace-with-a-random-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,testserver
```

The application reads these values through `python-dotenv`.

### Important

Do not commit real secrets, database passwords, API keys, or production
credentials to Git.

The repository's `.gitignore` excludes `.env`. If a `.env` file was
committed to a public repository, remove it from version control and
rotate any credentials that were stored in it.

The current settings file uses SQLite directly, so the `DB_*` variables
are not required by the current database configuration.

------------------------------------------------------------------------

## Initialize the database

Run:

``` bash
python manage.py migrate
```

This creates the Django tables and the application tables defined by the
migrations.

------------------------------------------------------------------------

## Import the fuel-price dataset

The repository contains:

``` text
data/fuel-prices-for-be-assessment.csv
```

Import it with:

``` bash
python manage.py import_fuel_prices --file data/fuel-prices-for-be-assessment.csv
```

The importer:

-   validates the required CSV columns;
-   creates or updates `FuelStation` records;
-   preserves every supplied price observation in
    `FuelPriceObservation`;
-   uses the source row number to make repeated imports idempotent;
-   treats the last source observation encountered for a station as its
    effective price because the supplied CSV has no observation
    timestamp.

If a custom CSV is used:

``` bash
python manage.py import_fuel_prices --file path/to/your-file.csv
```

The CSV must contain these columns:

``` text
OPIS Truckstop ID
Truckstop Name
Address
City
State
Rack ID
Retail Price
```

------------------------------------------------------------------------

## Geocode the fuel stations

The API expects station coordinates to already exist in the database.
Geocoding is therefore an offline data-preparation step rather than part
of every route request.

Run:

``` bash
python manage.py geocode_stations --user-agent "FuelRouteOptimizer/1.0 (your-email@example.com)"
```

For a limited number of stations during development:

``` bash
python manage.py geocode_stations \
  --limit 100 \
  --delay 1.0 \
  --user-agent "FuelRouteOptimizer/1.0 (your-email@example.com)"
```

On Windows PowerShell, use the same command on one line if preferred:

``` powershell
python manage.py geocode_stations --limit 100 --delay 1.0 --user-agent "FuelRouteOptimizer/1.0 (your-email@example.com)"
```

### Why this command is slow

The command sends one external geocoding request per station and
defaults to a one-second delay between requests.

The supplied dataset contains thousands of station records. With
approximately 6,738 stations, the one-second delay alone represents
about 112 minutes of waiting time before network latency and request
processing are included.

This is intentional. The command is designed to avoid sending a large
burst of requests to a public geocoding service.

The command also skips stations that already have coordinates:

``` python
FuelStation.objects.filter(latitude__isnull=True)
```

Run geocoding as a data-preparation job and keep the resulting
coordinates in the database. Do not run this command as part of an API
request.

------------------------------------------------------------------------

## Start the development server

``` bash
python manage.py runserver
```

Open:

``` text
http://127.0.0.1:8000/
```

The root endpoint serves both the browser interface for manual testing
and the JSON API.

------------------------------------------------------------------------

# API

## Endpoint

``` text
POST /
Content-Type: application/json
```

Example request:

``` json
{
  "origin": "Chicago, IL",
  "destination": "Dallas, TX",
  "initial_fuel_gallons": 30,
  "origin_fuel_price": 3.0
}
```

### Request fields

  -------------------------------------------------------------------------------------
  Field                    Type                 Required          Default Description
  ------------------------ ------------ ---------------- ---------------- -------------
  `origin`                 string                    Yes              --- U.S. starting
                                                                          location

  `destination`            string                    Yes              --- U.S.
                                                                          destination

  `origin_fuel_price`      decimal                    No            `3.0` Price used
                                                                          for fuel
                                                                          consumed from
                                                                          the initial
                                                                          tank
                                                                          inventory

  `initial_fuel_gallons`   float                      No           `30.0` Fuel already
                                                                          in the tank
                                                                          at the start
                                                                          of the trip
  -------------------------------------------------------------------------------------

The current implementation accepts between `0` and `50` initial gallons.

> **Implementation note:** The executable code currently defaults to 30
> gallons. Older comments/tests in the repository refer to 10 gallons.
> If the intended business rule is 10 gallons, update the serializer,
> optimizer constant, UI default, tests, and documentation together
> before treating that value as final.

------------------------------------------------------------------------

## Example response

A successful response has this general structure:

``` json
{
  "origin": "Chicago, IL",
  "destination": "Dallas, TX",
  "route": {
    "distance_miles": 920.12,
    "duration_hours": 13.72,
    "geometry": [
      [-87.6298, 41.8781],
      [-87.50, 41.80]
    ]
  },
  "vehicle": {
    "max_range_miles": 500,
    "fuel_economy_mpg": 10
  },
  "fuel": {
    "gallons_used": 92.01,
    "gallons_purchased": 62.01,
    "initial_fuel_gallons": 30.0,
    "initial_fuel_used_gallons": 30.0,
    "initial_fuel_cost": 90.0,
    "origin_fuel_price": 3.0,
    "estimated_cost": 250.00
  },
  "stops": [
    {
      "truckstop_id": 123456,
      "name": "Example Station",
      "city": "Example City",
      "state": "IL",
      "retail_price": 3.19,
      "effective_price_policy": "latest_source_row",
      "latitude": 41.0,
      "longitude": -88.0,
      "distance_from_start_miles": 210.5,
      "gallons": 18.2,
      "estimated_cost": 58.06
    }
  ]
}
```

The exact route, distance, stations, and costs depend on the external
routing service and the local station dataset.

------------------------------------------------------------------------

## Using cURL

``` bash
curl -X POST http://127.0.0.1:8000/ \
  -H "Content-Type: application/json" \
  -d "{\"origin\":\"Chicago, IL\",\"destination\":\"Dallas, TX\",\"initial_fuel_gallons\":30,\"origin_fuel_price\":3.0}"
```

For PowerShell:

``` powershell
$body = @{
    origin = "Chicago, IL"
    destination = "Dallas, TX"
    initial_fuel_gallons = 30
    origin_fuel_price = 3.0
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

------------------------------------------------------------------------

## Using Python

``` python
import requests

payload = {
    "origin": "Chicago, IL",
    "destination": "Dallas, TX",
    "initial_fuel_gallons": 30,
    "origin_fuel_price": 3.0,
}

response = requests.post(
    "http://127.0.0.1:8000/",
    json=payload,
    timeout=30,
)

response.raise_for_status()
print(response.json())
```

------------------------------------------------------------------------

# How the route calculation works

The API does not calculate road networks itself.

### 1. Geocoding

Nominatim converts:

``` text
Chicago, IL
```

into:

``` text
longitude, latitude
```

The same process is performed for the destination.

### 2. Routing

The coordinates are sent to OSRM.

OSRM returns:

-   driving distance;
-   estimated duration;
-   route geometry.

The application requests simplified GeoJSON geometry because the
geometry is required for station matching and map rendering.

### 3. Station filtering

The application does not compare every fuel station against every route
segment immediately.

It first calculates a conservative geographic bounding box around the
route and asks the database for stations inside that box.

The default corridor width is 15 miles.

### 4. Route projection

Candidate stations are then compared with route segments.

Each station receives:

-   distance from the route;
-   position along the route in miles.

The station data is converted from a two-dimensional geographic problem
into an ordered one-dimensional sequence:

``` text
Origin
  |
  +-- Station A @ 120 mi
  |
  +-- Station B @ 280 mi
  |
  +-- Station C @ 470 mi
  |
  +-- Destination @ 700 mi
```

### 5. Fuel optimization

The vehicle model is:

``` text
Fuel economy:     10 MPG
Tank capacity:    50 gallons
Maximum range:    500 miles
```

At each station, the optimizer looks for the first cheaper reachable
station.

If one exists, it purchases only enough fuel to reach that station.

If no cheaper reachable station exists, it purchases enough fuel to
reach the farthest useful reachable node without exceeding the
tank/range constraint.

This avoids evaluating every possible combination of fuel purchases.

------------------------------------------------------------------------

# External services and libraries

The application uses the following external components for specific
responsibilities:

  Component                 Purpose
  ------------------------- --------------------------------------------------------
  Nominatim                 Geocoding human-readable U.S. locations
  OSRM                      Driving route calculation
  OpenStreetMap             Geographic data used by the mapping/routing stack
  Leaflet                   Rendering the route and station markers in the browser
  Django                    Web application framework
  Django REST Framework     Request validation and API responses
  SQLite                    Local development database
  `requests`                HTTP communication with external services
  `urllib3` retry support   Retries for transient GET failures
  `python-dotenv`           Environment-variable loading

The fuel optimization logic, station filtering, route projection, cost
calculations, caching policy, and API orchestration are implemented
inside this repository.

------------------------------------------------------------------------

# Caching

The application uses Django's local-memory cache in the current
configuration.

## Geocoding cache

Geocoded locations are cached for 24 hours.

This prevents repeated requests for the same normalized location string.

## Route cache

OSRM routes are cached for 6 hours.

The cache key is based on the resolved origin and destination
coordinates.

## Complete-result cache

The final optimization response is cached for 15 minutes.

A repeated request with the same:

-   origin;
-   destination;
-   origin fuel price;
-   initial fuel amount;

can therefore be returned without repeating station matching or fuel
optimization.

The response includes:

``` text
X-Result-Cache: HIT
```

or:

``` text
X-Result-Cache: MISS
```

This makes cache behavior visible during development.

The configured cache backend is:

``` python
django.core.cache.backends.locmem.LocMemCache
```

For multiple application processes or production deployments, use a
shared cache such as Redis.

------------------------------------------------------------------------

# Reliability and error handling

External services are not assumed to be reliable.

The routing service uses:

-   connection timeout: 3 seconds;
-   read timeout: 15 seconds;
-   limited retries for transient GET failures;
-   retry handling for HTTP 429, 500, 502, 503, and 504 responses;
-   `Retry-After` support;
-   explicit exception types for upstream failures.

The API maps failures to HTTP responses rather than exposing internal
exception details.

Typical responses include:

  Condition                       HTTP status
  ----------------------------- -------------
  Invalid request                       `400`
  Location not found                    `404`
  Upstream timeout                      `504`
  Upstream rate limit                   `503`
  Other upstream failure                `502`
  Unexpected internal failure           `500`

------------------------------------------------------------------------

# Database model

The application separates physical stations from price observations.

``` text
FuelStation
    |
    +---- FuelPriceObservation
    +---- FuelPriceObservation
    +---- FuelPriceObservation
```

`FuelStation` stores the physical station identity and its effective
retail price.

`FuelPriceObservation` stores each supplied source-row observation.

The source CSV does not contain timestamps. Therefore the importer uses
the highest source row encountered for a station as the effective price.

The application also stores latitude and longitude on `FuelStation` so
normal API requests do not need to geocode every station.

------------------------------------------------------------------------

# Performance and complexity

Let:

-   `G` = number of route geometry points;
-   `S` = number of candidate stations after database corridor
    filtering.

The major local operations have the following worst-case complexity:

  Operation                                         Complexity
  --------------------------------------- --------------------
  Route cumulative-distance calculation                 `O(G)`
  Station-to-route projection                       `O(S × G)`
  Station sorting                                 `O(S log S)`
  Current greedy search implementation      `O(S²)` worst case

The local optimization pipeline is therefore approximately:

``` text
O(S × G + S² + S log S)
```

The external calls to Nominatim and OSRM are network-bound and are not
meaningfully represented by the local algorithmic complexity.

## Practical performance strategy

The application reduces the amount of work before expensive operations:

``` text
All stored stations
      |
      v
Database geographic filter
      |
      v
Small candidate set
      |
      v
Route projection
      |
      v
Ordered route stations
      |
      v
Greedy optimizer
```

This is more important than micro-optimizing individual Python
calculations.

The route geometry is also requested in simplified form to keep the
number of geometry points manageable.

### Response time

The repository does not contain a production load-test benchmark, so no
fixed average API response time is claimed.

A cold request is dominated by external geocoding and OSRM network
latency.

A complete-result cache hit avoids those operations and should be
substantially faster.

If response-time numbers are required for deployment decisions,
benchmark the running deployment with representative routes and record:

-   p50;
-   p95;
-   p99;
-   cache-hit latency;
-   cache-miss latency;
-   upstream failure rate.

------------------------------------------------------------------------

# Running tests

Run the full Django test suite with:

``` bash
python manage.py test
```

The test suite covers:

-   request validation;
-   same-origin/destination validation;
-   location-not-found handling;
-   upstream timeout handling;
-   upstream rate-limit handling;
-   upstream service failures;
-   zero-distance trips;
-   initial-fuel accounting;
-   the 500-mile range boundary;
-   stations beyond the maximum range;
-   cheaper reachable stations;
-   equal-price stations;
-   multi-stop trips;
-   long deterministic routes;
-   duplicate price observations;
-   effective-price selection;
-   idempotent data imports.

Before relying on the test result, install the pinned dependencies with:

``` bash
pip install -r requirements.txt
```

------------------------------------------------------------------------

# Common commands

### Install dependencies

``` bash
pip install -r requirements.txt
```

### Apply migrations

``` bash
python manage.py migrate
```

### Import fuel prices

``` bash
python manage.py import_fuel_prices --file data/fuel-prices-for-be-assessment.csv
```

### Geocode stations

``` bash
python manage.py geocode_stations --user-agent "FuelRouteOptimizer/1.0 (your-email@example.com)"
```

### Run the development server

``` bash
python manage.py runserver
```

### Run tests

``` bash
python manage.py test
```

### Check Django configuration

``` bash
python manage.py check
```

------------------------------------------------------------------------

# Development notes

## Station geocoding should remain an offline operation

Do not move station geocoding into the route request path.

A user request should not trigger thousands of external geocoding calls.
Coordinates should be populated during data ingestion and reused by the
API.

For larger datasets, useful improvements include:

-   deduplicating identical addresses before geocoding;
-   persisting geocoding results;
-   adding a dedicated geocoding cache;
-   running geocoding as a background job;
-   using a provider appropriate for the required request volume.

## Production database

SQLite is suitable for local development and the included dataset.

For a multi-user production deployment, PostgreSQL is a more appropriate
database. For larger geographic workloads, PostGIS can also move more
spatial filtering into the database.

## Production cache

The current local-memory cache is process-local.

For multiple workers or multiple application instances, use a shared
cache such as Redis.

## API protection

If the endpoint is exposed publicly, add controls appropriate to the
deployment, including:

-   HTTPS;
-   production `SECRET_KEY`;
-   restricted `ALLOWED_HOSTS`;
-   API rate limiting;
-   authentication if the endpoint is not public;
-   production cache configuration;
-   structured logging;
-   application metrics;
-   upstream usage controls.

------------------------------------------------------------------------

# Design decisions

### Why Nominatim?

The API accepts human-readable locations, while routing requires
coordinates. Nominatim provides the geocoding step without putting
geocoding logic inside the Django application.

### Why OSRM?

Road routing is a separate concern from the web application. OSRM
provides driving distance, duration, and route geometry, which the
application then uses for station matching and fuel planning.

### Why a corridor filter?

The database may contain thousands of stations across the U.S. Most are
irrelevant to a particular route. A geographic prefilter reduces the
number of stations that need precise route-distance calculations.

### Why project stations onto the route?

Fuel decisions depend on where a station occurs along the trip, not only
on its latitude and longitude. Projecting a station onto the route gives
the optimizer a single route-distance value.

### Why a greedy algorithm?

With fixed fuel economy, fixed tank capacity, known station prices, and
a one-dimensional route, the fuel decision can be reduced to a sequence
of reachable stations. The optimizer can therefore make a local decision
based on the first cheaper reachable station instead of enumerating
every possible purchase combination.

### Why cache?

Geocoding and routing are external network operations. They are more
expensive and less predictable than local calculations. Caching prevents
repeated requests for the same geographic data and repeated optimization
of identical inputs.

------------------------------------------------------------------------

# Limitations

This repository intentionally uses a fixed vehicle model:

``` text
10 MPG
50-gallon tank
500-mile maximum range
```

The fuel model does not currently account for:

-   changing MPG due to speed or terrain;
-   traffic-dependent fuel consumption;
-   vehicle load;
-   diesel/gasoline distinctions;
-   taxes or fees not represented in the source price;
-   station operating hours;
-   live fuel-price updates;
-   real-time station availability;
-   road closures after route calculation;
-   multiple route alternatives.

Station prices are also limited by the supplied dataset. Because the
source does not contain observation timestamps, the application cannot
determine the actual real-world age of a price.

The route and geocoding results depend on the availability and behavior
of the configured external services.

------------------------------------------------------------------------

# License

Add the license appropriate for your project before publishing the
repository.

If this repository is intended for public use, also review the terms and
usage policies of the external services and data sources used by the
application.

------------------------------------------------------------------------

# Summary

This project separates the system into four main responsibilities:

``` text
Geocoding
    Nominatim

Routing
    OSRM

Station selection
    Django ORM + geographic filtering + route projection

Fuel planning
    Greedy optimization
```

Django coordinates those components, stores the station data, exposes
the HTTP API, and handles validation, caching, and errors.

The expensive data-preparation task---geocoding the station dataset---is
intentionally performed offline. Once station coordinates are stored,
normal route requests operate on local station data and only need the
origin/destination geocoding and route lookup when the relevant caches
are cold.
