import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from routes.models import FuelStation


class Command(BaseCommand):
    help = "Import fuel station prices from the supplied CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            help="Path to the fuel price CSV file.",
        )

    def handle(self, *args, **options):
        csv_path = self.get_csv_path(options.get("file"))

        if not csv_path.exists():
            raise CommandError(
                f"CSV file not found: {csv_path}"
            )

        self.stdout.write(
            self.style.NOTICE(
                f"Importing fuel prices from: {csv_path}"
            )
        )

        created_count = 0
        updated_count = 0
        skipped_count = 0

        with csv_path.open(
            mode="r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:

            reader = csv.DictReader(csv_file)

            required_columns = {
                "OPIS Truckstop ID",
                "Truckstop Name",
                "Address",
                "City",
                "State",
                "Rack ID",
                "Retail Price",
            }

            missing_columns = required_columns - set(reader.fieldnames or [])

            if missing_columns:
                raise CommandError(
                    "Missing CSV columns: "
                    + ", ".join(sorted(missing_columns))
                )

            with transaction.atomic():

                for row_number, row in enumerate(reader, start=2):

                    try:
                        truckstop_id = int(
                            row["OPIS Truckstop ID"]
                        )

                        name = row["Truckstop Name"].strip()
                        address = row["Address"].strip()
                        city = row["City"].strip()
                        state = row["State"].strip().upper()
                        rack_id = row["Rack ID"].strip()

                        retail_price = Decimal(
                            row["Retail Price"].strip()
                        )

                    except (
                        ValueError,
                        InvalidOperation,
                        AttributeError,
                    ) as exc:

                        skipped_count += 1

                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping row {row_number}: {exc}"
                            )
                        )

                        continue

                    if not name or not city or not state:
                        skipped_count += 1

                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping row {row_number}: "
                                "missing required station information."
                            )
                        )

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
                        created_count += 1
                    else:
                        updated_count += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Fuel price import completed successfully."
            )
        )

        self.stdout.write(
            f"Created: {created_count}"
        )

        self.stdout.write(
            f"Updated: {updated_count}"
        )

        self.stdout.write(
            f"Skipped: {skipped_count}"
        )

    def get_csv_path(self, provided_path):
        if provided_path:
            return Path(provided_path)

        base_dir = Path(__file__).resolve().parents[3]

        return (
            base_dir
            / "data"
            / "fuel-prices-for-be-assessment.csv"
        )