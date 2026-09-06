from django.test import TestCase
from routes.services.fuel_optimizer import optimize_fuel_stops

class FuelOptimizerTests(TestCase):
    def test_short_route_no_stops(self):
        route_data = {
            "distance_miles": 350.0,
            "duration_hours": 5.0,
            "geometry": [[-87.6298, 41.8781], [-89.6501, 39.7817]]
        }
        plan = optimize_fuel_stops(route_data)
        
        self.assertEqual(len(plan["stops"]), 0)
        self.assertEqual(plan["total_gallons"], 35.0)
        self.assertEqual(plan["total_cost"], 0.0)