import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


class PocketSmartAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.previous_path = settings.database_path
        object.__setattr__(settings, "database_path", Path(cls.tempdir.name) / "test.sqlite3")
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        object.__setattr__(settings, "database_path", cls.previous_path)
        cls.tempdir.cleanup()

    def test_home_and_health(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

    def test_demo_home_recommendation_respects_budget(self):
        response = self.client.post("/api/recommendations/home", data={
            "payload": json.dumps({"budget": 25000, "room_types": "Living room", "style": "Minimal"})
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["source"], "Demo estimate")
        self.assertLessEqual(sum(item["estimated_price"] for item in result["items"]), 25000)

    def test_validation_and_unknown_planner(self):
        too_small = self.client.post("/api/recommendations/home", data={"payload": json.dumps({"budget": 0, "room_types": "Room"})})
        self.assertEqual(too_small.status_code, 422)
        missing_room = self.client.post("/api/recommendations/home", data={"payload": json.dumps({"budget": 1000})})
        self.assertEqual(missing_room.status_code, 422)
        unknown = self.client.post("/api/recommendations/unknown", data={"payload": "{}"})
        self.assertEqual(unknown.status_code, 404)

    def test_jewelry_image_type_and_demo_plan(self):
        payload = json.dumps({"budget": 5000, "occasion": "Wedding", "style": "Classic"})
        invalid_image = self.client.post("/api/recommendations/jewelry", data={"payload": payload},
            files={"image": ("outfit.png", b"not a png", "image/png")})
        self.assertEqual(invalid_image.status_code, 415)
        response = self.client.post("/api/recommendations/jewelry", data={"payload": payload})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertLessEqual(sum(item["estimated_price"] for item in result["items"]), result["total_budget"])

    def test_register_history_and_logout(self):
        registered = self.client.post("/api/register", json={
            "email": "reader@example.com", "display_name": "Reader", "password": "A-strong-passphrase-42"
        })
        self.assertEqual(registered.status_code, 201, registered.text)
        self.assertTrue(self.client.get("/api/session").json()["user"])
        result = self.client.post("/api/recommendations/party", data={
            "payload": json.dumps({"budget": 15000, "event_type": "Birthday", "guests": 12})
        })
        self.assertEqual(result.status_code, 200, result.text)
        history = self.client.get("/api/history")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()["items"]), 1)
        self.client.post("/api/logout")
        self.assertIsNone(self.client.get("/api/session").json()["user"])


if __name__ == "__main__":
    unittest.main()
