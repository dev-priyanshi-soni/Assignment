from django.test import SimpleTestCase
from routes.services.optimizer import build_fuel_plan

class OptimizerTests(SimpleTestCase):

    def test_short_route_needs_no_stop(self):
        result = build_fuel_plan([], 300, 500, 10, 50)
        self.assertEqual(result["stops"], [])
        self.assertEqual(result["total_cost"], 0.0)

    def test_long_route_requires_stops(self):
        stations = [
            {
                "truckstop_id": "1",
                "name": "A",
                "address": "I-1",
                "city": "A",
                "state": "TX",
                "price": 3.0,
                "latitude": 30.0,
                "longitude": -97.0,
                "route_position_miles": 450,
                "distance_from_route_miles": 2,
            },
            {
                "truckstop_id": "2",
                "name": "B",
                "address": "I-2",
                "city": "B",
                "state": "TX",
                "price": 3.2,
                "latitude": 31.0,
                "longitude": -96.0,
                "route_position_miles": 800,
                "distance_from_route_miles": 2,
            },
        ]
        result = build_fuel_plan(stations, 1000, 500, 10, 50)
        self.assertTrue(result["stops"])
