from rest_framework import status
from rest_framework.test import APITestCase


class RouteApiTests(APITestCase):
    def test_missing_fields_validation(self):
        response = self.client.post("/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_origin(self):
        payload = {
            "origin": "",
            "destination": "Dallas, TX"
        }
        response = self.client.post("/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
