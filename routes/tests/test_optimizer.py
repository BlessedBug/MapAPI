from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from routes.services.fuel_optimizer import optimize_fuel_stops


def station(identifier, price):
    return SimpleNamespace(
        truckstop_id=identifier,
        name=f"Station {identifier}",
        city="Test City",
        state="TS",
        retail_price=price,
        latitude=0.0,
        longitude=0.0,
    )


class FuelOptimizerTests(TestCase):
    def route(self, distance):
        return {
            "distance_miles": distance,
            "duration_hours": 0.0,
            "geometry": [[0, 0], [1, 1]],
        }

    @patch("routes.services.fuel_optimizer._snap_stations")
    def test_short_route_charges_fuel(self, snap):
        snap.return_value = [
            {"station": station(1, 3.0), "route_dist": 100.0}
        ]
        plan = optimize_fuel_stops(
            self.route(300.0),
            origin_fuel_price=3.0
        )
        self.assertEqual(plan["total_gallons"], 30.0)
        self.assertEqual(plan["total_cost"], 90.0)
        self.assertEqual(plan["stops"], [])

    @patch("routes.services.fuel_optimizer._snap_stations")
    def test_final_leg_is_included(self, snap):
        snap.return_value = [
            {"station": station(1, 4.0), "route_dist": 400.0}
        ]
        plan = optimize_fuel_stops(
            self.route(700.0),
            origin_fuel_price=4.0
        )
        self.assertEqual(plan["total_cost"], 40.0 + 120.0 + 120.0)
        self.assertEqual(len(plan["stops"]), 1)
        self.assertEqual(plan["stops"][0]["gallons"], 30.0)

    @patch("routes.services.fuel_optimizer._snap_stations")
    def test_cheaper_reachable_station_means_buy_only_enough_to_reach_it(self, snap):
        expensive = station(1, 4.0)
        cheap = station(2, 2.0)
        snap.return_value = [
            {"station": expensive, "route_dist": 100.0},
            {"station": cheap, "route_dist": 400.0},
        ]
        plan = optimize_fuel_stops(
            self.route(700.0),
            origin_fuel_price=4.0
        )
        self.assertEqual(plan["total_cost"], 40.0 + 120.0 + 60.0)
        self.assertEqual(len(plan["stops"]), 1)
        self.assertEqual(plan["stops"][0]["truckstop_id"], 2)
        self.assertEqual(plan["stops"][0]["gallons"], 30.0)

    @patch("routes.services.fuel_optimizer._snap_stations")
    def test_no_cheaper_station_fills_tank_and_skips_expensive_stop(self, snap):
        first = station(1, 3.0)
        second = station(2, 4.0)
        snap.return_value = [
            {"station": first, "route_dist": 200.0},
            {"station": second, "route_dist": 400.0},
        ]
        plan = optimize_fuel_stops(
            self.route(800.0),
            origin_fuel_price=3.0
        )
        self.assertEqual(plan["total_gallons"], 80.0)
        self.assertGreater(plan["total_cost"], 0.0)

    @patch("routes.services.fuel_optimizer._snap_stations", return_value=[])
    def test_route_beyond_tank_range_without_station_is_infeasible(self, _):
        with self.assertRaises(ValueError):
            optimize_fuel_stops(
                self.route(500.1),
                origin_fuel_price=3.0
            )

    def test_zero_distance_has_zero_cost(self):
        plan = optimize_fuel_stops(
            {
                "distance_miles": 0.0,
                "duration_hours": 0.0,
                "geometry": [],
            },
            origin_fuel_price=3.0,
        )
        self.assertEqual(plan["total_gallons"], 0.0)
        self.assertEqual(plan["total_cost"], 0.0)

    @patch("routes.services.fuel_optimizer._snap_stations", return_value=[])
    def test_initial_fuel_can_cover_trip_without_station_and_is_costed_when_used(self, _):
        plan = optimize_fuel_stops(
            self.route(300.0),
            origin_fuel_price=3.0,
            initial_fuel_gallons=30.0,
        )
        self.assertEqual(plan["total_cost"], 90.0)
        self.assertEqual(plan["initial_fuel_cost"], 90.0)
        self.assertEqual(plan["initial_fuel_used_gallons"], 30.0)
        self.assertEqual(plan["gallons_purchased"], 0.0)
        self.assertEqual(plan["total_gallons"], 30.0)

    @patch("routes.services.fuel_optimizer._snap_stations", return_value=[])
    def test_default_starting_inventory_is_thirty_gallons_at_three_dollars(self, _):
        plan = optimize_fuel_stops(self.route(100.0))
        self.assertEqual(plan["initial_fuel_gallons"], 30.0)
        self.assertEqual(plan["origin_fuel_price"], 3.0)
        self.assertEqual(plan["initial_fuel_used_gallons"], 10.0)
        self.assertEqual(plan["initial_fuel_cost"], 30.0)
        self.assertEqual(plan["total_cost"], 30.0)
        self.assertEqual(plan["gallons_purchased"], 0.0)

    @patch("routes.services.fuel_optimizer._snap_stations", return_value=[])
    def test_unused_initial_fuel_is_not_charged_to_trip(self, _):
        plan = optimize_fuel_stops(self.route(50.0))
        self.assertEqual(plan["initial_fuel_used_gallons"], 5.0)
        self.assertEqual(plan["initial_fuel_cost"], 15.0)
        self.assertEqual(plan["total_cost"], 15.0)

    def test_invalid_initial_fuel_is_rejected(self):
        with self.assertRaises(ValueError):
            optimize_fuel_stops(
                self.route(100.0),
                origin_fuel_price=3.0,
                initial_fuel_gallons=51.0,
            )


class FuelOptimizerEdgeCaseTests(TestCase):
    def route(self, distance):
        return {
            "distance_miles": distance,
            "duration_hours": 0.0,
            "geometry": [[0, 0], [1, 1]],
        }

    @patch("routes.services.fuel_optimizer._snap_stations", return_value=[])
    def test_300_mile_route_needs_no_station_when_origin_can_supply_fuel(self, _):
        plan = optimize_fuel_stops(self.route(300.0))
        self.assertEqual(plan["total_gallons"], 30.0)
        self.assertEqual(plan["initial_fuel_used_gallons"], 30.0)
        self.assertEqual(plan["gallons_purchased"], 0.0)
        self.assertEqual(plan["stops"], [])

    @patch("routes.services.fuel_optimizer._snap_stations", return_value=[])
    def test_stationless_route_beyond_500_miles_is_infeasible(self, _):
        with self.assertRaisesRegex(ValueError, "500-mile"):
            optimize_fuel_stops(self.route(500.1))

    @patch("routes.services.fuel_optimizer._snap_stations")
    def test_station_exactly_500_miles_away_is_reachable(self, snap):
        snap.return_value = [
            {"station": station(1, 3.0), "route_dist": 500.0}
        ]
        plan = optimize_fuel_stops(self.route(700.0))
        self.assertEqual(plan["total_gallons"], 70.0)
        self.assertTrue(plan["stops"])

    @patch("routes.services.fuel_optimizer._snap_stations")
    def test_station_beyond_500_miles_is_not_reachable_from_origin(self, snap):
        snap.return_value = [
            {"station": station(1, 3.0), "route_dist": 500.1}
        ]
        with self.assertRaisesRegex(ValueError, "500-mile"):
            optimize_fuel_stops(self.route(700.0))

    @patch("routes.services.fuel_optimizer._snap_stations")
    def test_equal_price_station_does_not_improve_cost(self, snap):
        snap.return_value = [
            {"station": station(1, 3.0), "route_dist": 200.0},
            {"station": station(2, 3.0), "route_dist": 450.0},
        ]
        plan = optimize_fuel_stops(self.route(800.0))
        self.assertEqual(plan["total_gallons"], 80.0)
        self.assertGreaterEqual(plan["total_cost"], 240.0)

    @patch("routes.services.fuel_optimizer._snap_stations")
    def test_2000_mile_route_is_feasible_and_accounts_for_all_fuel(self, snap):
        snap.return_value = [
            {"station": station(1, 4.0), "route_dist": 300.0},
            {"station": station(2, 2.8), "route_dist": 700.0},
            {"station": station(3, 4.2), "route_dist": 1100.0},
            {"station": station(4, 2.6), "route_dist": 1500.0},
        ]
        plan = optimize_fuel_stops(self.route(2000.0))
        self.assertEqual(plan["total_gallons"], 200.0)
        self.assertEqual(plan["initial_fuel_used_gallons"], 30.0)
        self.assertAlmostEqual(plan["gallons_purchased"], 170.0, places=2)
        self.assertTrue(plan["stops"])
        self.assertGreater(plan["total_cost"], 0.0)
