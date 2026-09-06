from django.core.management.base import BaseCommand
from routes.models import FuelStation

import geonamescache


class Command(BaseCommand):
    help = (
        "Populate missing US fuel station coordinates using "
        "city/state coordinates from GeoNames."
    )

    CANADIAN_PROVINCES = {
        "AB", "BC", "MB", "NB", "NL",
        "NS", "NT", "NU", "ON", "PE",
        "QC", "SK", "YT",
    }

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.NOTICE(
                "Building US city/state coordinate lookup..."
            )
        )

        gc = geonamescache.GeonamesCache()
        cities = gc.get_cities()

        city_lookup = {}

        for city in cities.values():
            if city.get("countrycode") != "US":
                continue

            name = self.normalize(city.get("name", ""))
            admin1 = city.get("admin1code", "")

            if not name or not admin1:
                continue

            key = (name, admin1)

            latitude = city.get("latitude")
            longitude = city.get("longitude")

            if latitude is None or longitude is None:
                continue

            # If multiple GeoNames entries exist for the same
            # city/state, keep the first usable coordinate.
            if key not in city_lookup:
                city_lookup[key] = (
                    float(latitude),
                    float(longitude),
                )

        self.stdout.write(
            f"US city/state coordinates available: "
            f"{len(city_lookup)}"
        )

        stations = (
            FuelStation.objects
            .filter(
                latitude__isnull=True,
                longitude__isnull=True,
            )
            .exclude(
                state__in=self.CANADIAN_PROVINCES
            )
        )

        total = stations.count()

        self.stdout.write(
            f"US stations requiring coordinates: {total}"
        )

        updated = 0
        unmatched = 0

        for station in stations.iterator():
            city = self.normalize(station.city)
            state = station.state.strip().upper()

            key = (city, state)

            coordinates = city_lookup.get(key)

            if coordinates is None:
                unmatched += 1
                continue

            latitude, longitude = coordinates

            FuelStation.objects.filter(
                pk=station.pk
            ).update(
                latitude=latitude,
                longitude=longitude,
            )

            updated += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Coordinate population completed."
            )
        )

        self.stdout.write(
            f"Updated: {updated}"
        )

        self.stdout.write(
            f"Unmatched: {unmatched}"
        )

        self.stdout.write(
            f"Already had coordinates: "
            f"{FuelStation.objects.filter(latitude__isnull=False).count()}"
        )

    @staticmethod
    def normalize(value):
        return " ".join(
            value.strip().lower().split()
        )