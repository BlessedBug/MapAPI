import time

import requests
from django.core.management.base import BaseCommand, CommandError

from routes.models import FuelStation


class Command(BaseCommand):
    help = "Geocode stations individually from their address/city/state using Nominatim."
    SEARCH_URL = "https://nominatim.openstreetmap.org/search"
    TIMEOUT = (5, 20)

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--delay", type=float, default=1.0)
        parser.add_argument("--user-agent", required=True)

    def handle(self, *args, **options):
        limit = options["limit"]
        delay = max(0.0, options["delay"])
        headers = {"User-Agent": options["user_agent"]}
        stations = FuelStation.objects.filter(latitude__isnull=True).order_by("pk")
        if limit:
            stations = stations[:limit]

        updated = unmatched = failed = 0
        for station in stations.iterator() if not limit else stations:
            query = ", ".join(part for part in [station.address, station.city, station.state, "USA"] if part)
            try:
                response = requests.get(
                    self.SEARCH_URL,
                    params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
                    headers=headers,
                    timeout=self.TIMEOUT,
                )
                response.raise_for_status()
                results = response.json()
            except (requests.RequestException, ValueError) as exc:
                failed += 1
                self.stderr.write(f"{station.pk}: geocoding failed: {exc}")
                if delay:
                    time.sleep(delay)
                continue

            if not results:
                unmatched += 1
            else:
                result = results[0]
                try:
                    station.latitude = float(result["lat"])
                    station.longitude = float(result["lon"])
                except (KeyError, TypeError, ValueError):
                    unmatched += 1
                else:
                    station.coordinate_source = "nominatim_address"
                    station.save(update_fields=["latitude", "longitude", "coordinate_source", "updated_at"])
                    updated += 1
            if delay:
                time.sleep(delay)

        self.stdout.write(self.style.SUCCESS(
            f"Geocoding completed. Updated={updated}, unmatched={unmatched}, failed={failed}"
        ))
