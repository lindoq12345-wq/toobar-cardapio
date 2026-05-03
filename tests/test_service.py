import unittest
import uuid
from pathlib import Path

from toobar.service import AppError, ToobarService


class ToobarServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path(__file__).resolve().parents[1] / ".testdata"
        self.tmp_root.mkdir(exist_ok=True)
        self.db_path = self.tmp_root / f"{self._testMethodName}-{uuid.uuid4().hex}.sqlite3"
        self.service = ToobarService(self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_register_creates_user_and_session(self):
        result = self.service.register("Ana", "ANA@example.com", "segredo1")

        self.assertEqual(result["user"]["email"], "ana@example.com")
        self.assertTrue(result["token"])
        self.assertEqual(self.service.current_user(result["token"])["name"], "Ana")

    def test_login_rejects_wrong_password(self):
        self.service.register("Ana", "ana@example.com", "segredo1")

        with self.assertRaises(AppError) as ctx:
            self.service.login("ana@example.com", "errada")

        self.assertEqual(ctx.exception.status, 401)

    def test_menu_is_seeded_and_filterable(self):
        all_items = self.service.menu()
        drinks = self.service.menu("drinks")

        self.assertGreaterEqual(len(all_items), 8)
        self.assertTrue(drinks)
        self.assertTrue(all(item["category"] == "drinks" for item in drinks))

    def test_order_requires_authentication(self):
        item = self.service.menu()[0]

        with self.assertRaises(AppError) as ctx:
            self.service.create_order(None, {
                "table_label": "Mesa 3",
                "items": [{"menu_item_id": item["id"], "quantity": 1}],
            })

        self.assertEqual(ctx.exception.status, 401)

    def test_authenticated_user_can_create_order(self):
        auth = self.service.register("Ana", "ana@example.com", "segredo1")
        item = self.service.menu()[0]

        order = self.service.create_order(auth["token"], {
            "table_label": "Mesa 3",
            "notes": "sem cebola",
            "items": [{"menu_item_id": item["id"], "quantity": 2}],
        })

        self.assertEqual(order["table_label"], "Mesa 3")
        self.assertEqual(order["items"][0]["quantity"], 2)
        self.assertEqual(order["total"], round(item["price"] * 2, 2))

    def test_order_rejects_invalid_quantity(self):
        auth = self.service.register("Ana", "ana@example.com", "segredo1")
        item = self.service.menu()[0]

        with self.assertRaises(AppError):
            self.service.create_order(auth["token"], {
                "table_label": "Mesa 3",
                "items": [{"menu_item_id": item["id"], "quantity": 0}],
            })


if __name__ == "__main__":
    unittest.main()
