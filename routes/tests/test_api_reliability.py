from unittest.mock import patch

import requests
from rest_framework import status
from rest_framework.test import APITestCase

from routes.services.routing_service import (
    LocationNotFoundError,
    UpstreamRateLimitError,
    UpstreamServiceError,
    UpstreamTimeoutError,
)


class RouteApiReliabilityTests(APITestCase):
    def test_same_origin_and_destination_is_rejected_before_upstream_call(self):
        response = self.client.post(
            "/",
            {"origin": "Chicago, IL", "destination": "Chicago, IL"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("routes.views.get_osrm_route", side_effect=LocationNotFoundError("not found"))
    def test_location_not_found_returns_404(self, _mock_route):
        response = self.client.post(
            "/",
            {"origin": "Nowhere", "destination": "Dallas, TX"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("routes.views.get_osrm_route", side_effect=UpstreamTimeoutError())
    def test_timeout_returns_504(self, _mock_route):
        response = self.client.post(
            "/",
            {"origin": "Chicago, IL", "destination": "Dallas, TX"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_504_GATEWAY_TIMEOUT)

    @patch("routes.views.get_osrm_route", side_effect=UpstreamRateLimitError())
    def test_rate_limit_returns_503(self, _mock_route):
        response = self.client.post(
            "/",
            {"origin": "Chicago, IL", "destination": "Dallas, TX"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @patch("routes.views.get_osrm_route", side_effect=UpstreamServiceError())
    def test_upstream_failure_returns_502_without_details(self, _mock_route):
        response = self.client.post(
            "/",
            {"origin": "Chicago, IL", "destination": "Dallas, TX"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertNotIn("Traceback", str(response.data))
