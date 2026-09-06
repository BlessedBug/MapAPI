from django.test import TestCase

from routes.services.cost_calculator import (
    calculate_fuel_gallons,
    calculate_stop_cost,
    calculate_total_cost,
)


class CostCalculatorTests(TestCase):
    def test_gallons_calculation(self):
        self.assertEqual(calculate_fuel_gallons(100.0, 10.0), 10.0)
        self.assertEqual(calculate_fuel_gallons(455.5, 10.0), 45.55)

    def test_stop_cost(self):
        self.assertEqual(calculate_stop_cost(10.0, 3.50), 35.0)

    def test_total_cost(self):
        stops = [{"estimated_cost": 50.25}, {"estimated_cost": 49.75}]
        self.assertEqual(calculate_total_cost(stops), 100.0)
