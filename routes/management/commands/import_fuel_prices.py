import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from routes.models import FuelPriceObservation, FuelStation


class Command(BaseCommand):
    help = "Import fuel stations and preserve every supplied retail-price observation."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, help="Path to the fuel price CSV file.")

    def handle(self, *args, **options):
        csv_path = self.get_csv_path(options.get("file"))
        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        self.stdout.write(self.style.NOTICE(f"Importing fuel prices from: {csv_path}"))

        created_stations = updated_stations = created_prices = existing_prices = skipped = 0

        with csv_path.open(mode="r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            required_columns = {
                "OPIS Truckstop ID", "Truckstop Name", "Address", "City",
                "State", "Rack ID", "Retail Price",
            }
            missing_columns = required_columns - set(reader.fieldnames or [])
            if missing_columns:
                raise CommandError("Missing CSV columns: " + ", ".join(sorted(missing_columns)))

            with transaction.atomic():
                for row_number, row in enumerate(reader, start=2):
                    try:
                        truckstop_id = int(row["OPIS Truckstop ID"])
                        name = row["Truckstop Name"].strip()
                        address = row["Address"].strip()
                        city = row["City"].strip()
                        state = row["State"].strip().upper()
                        rack_id = row["Rack ID"].strip()
                        retail_price = Decimal(row["Retail Price"].strip())
                    except (ValueError, InvalidOperation, AttributeError) as exc:
                        skipped += 1
                        self.stdout.write(self.style.WARNING(f"Skipping row {row_number}: {exc}"))
                        continue

                    if not name or not city or not state:
                        skipped += 1
                        self.stdout.write(self.style.WARNING(
                            f"Skipping row {row_number}: missing required station information."
                        ))
                        continue

                    station, created = FuelStation.objects.update_or_create(
                        truckstop_id=truckstop_id,
                        defaults={
                            "name": name,
                            "address": address,
                            "city": city,
                            "state": state,
                            "rack_id": rack_id or None,
                            "retail_price": retail_price,
                        },
                    )
                    if created:
                        created_stations += 1
                    else:
                        updated_stations += 1

                    _, price_created = FuelPriceObservation.objects.get_or_create(
                        station=station,
                        source_row=row_number,
                        defaults={"retail_price": retail_price},
                    )
                    if price_created:
                        created_prices += 1
                    else:
                        existing_prices += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Fuel price import completed successfully."))
        self.stdout.write(f"Stations created: {created_stations}")
        self.stdout.write(f"Stations updated: {updated_stations}")
        self.stdout.write(f"Price observations created: {created_prices}")
        self.stdout.write(f"Price observations already present: {existing_prices}")
        self.stdout.write(f"Skipped: {skipped}")

    def get_csv_path(self, provided_path):
        if provided_path:
            return Path(provided_path)
        base_dir = Path(__file__).resolve().parents[3]
        return base_dir / "data" / "fuel-prices-for-be-assessment.csv"
