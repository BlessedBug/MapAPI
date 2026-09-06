from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

from django.core.management import call_command
from django.test import TestCase

from routes.models import FuelPriceObservation, FuelStation


class FuelPriceImportTests(TestCase):
    def write_csv(self, contents):
        handle = NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
            encoding="utf-8",
        )
        handle.write(contents)
        handle.close()
        self.addCleanup(
            lambda: Path(handle.name).unlink(missing_ok=True)
        )
        return handle.name

    def test_duplicate_station_id_preserves_all_price_observations(self):
        csv_path = self.write_csv(
            "OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price\n"
            "105,Test Stop,1 Main St,Testville,TX,R1,3.269\n"
            "105,Test Stop,1 Main St,Testville,TX,R1,3.429\n"
        )

        call_command("import_fuel_prices", file=csv_path)

        self.assertEqual(FuelStation.objects.count(), 1)
        self.assertEqual(FuelPriceObservation.objects.count(), 2)

        station = FuelStation.objects.get(truckstop_id=105)
        prices = list(
            station.price_observations.values_list(
                "retail_price",
                flat=True,
            )
        )
        self.assertEqual(
            prices,
            [
                Decimal("3.269"),
                Decimal("3.429"),
            ],
        )
        self.assertEqual(
            station.retail_price,
            Decimal("3.429"),
        )

    def test_reimport_is_idempotent_for_same_source_rows(self):
        csv_path = self.write_csv(
            "OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price\n"
            "105,Test Stop,1 Main St,Testville,TX,R1,3.269\n"
            "105,Test Stop,1 Main St,Testville,TX,R1,3.429\n"
        )

        call_command("import_fuel_prices", file=csv_path)
        call_command("import_fuel_prices", file=csv_path)

        self.assertEqual(FuelStation.objects.count(), 1)
        self.assertEqual(FuelPriceObservation.objects.count(), 2)

    def test_latest_source_row_is_explicit_effective_price_policy(self):
        csv_path = self.write_csv(
            "OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price\n"
            "105,Test Stop,1 Main St,Testville,TX,R1,3.269\n"
            "105,Test Stop,1 Main St,Testville,TX,R1,2.999\n"
            "105,Test Stop,1 Main St,Testville,TX,R1,3.199\n"
        )

        call_command("import_fuel_prices", file=csv_path)

        station = FuelStation.objects.get(truckstop_id=105)

        self.assertEqual(
            station.effective_price_policy,
            "latest_source_row",
        )
        self.assertEqual(
            station.get_effective_price(),
            Decimal("3.199"),
        )
        self.assertEqual(
            station.retail_price,
            Decimal("3.199"),
        )
