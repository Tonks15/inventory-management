"""
Tests for the restocking endpoints.
"""
import pytest

from mock_data import restock_orders


@pytest.fixture(autouse=True)
def clear_restock_orders():
    """Restock orders live in a module-level list, so reset it around every test."""
    restock_orders.clear()
    yield
    restock_orders.clear()


class TestRestockingItems:
    def test_returns_items_with_cost_and_lead_time(self, client):
        response = client.get("/api/restocking/items")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 9
        for item in data:
            assert item["unit_cost"] > 0
            assert item["lead_time_days"] > 0
            assert item["demand_gap"] == item["forecasted_demand"] - item["current_demand"]


class TestCreateRestockOrder:
    def test_creates_order_with_max_lead_time_and_total(self, client):
        items = {i["sku"]: i for i in client.get("/api/restocking/items").json()}
        payload = {"items": [
            {"sku": "FLT-405", "quantity": 100},
            {"sku": "BRG-102", "quantity": 10},
        ]}

        response = client.post("/api/restocking/orders", json=payload)

        assert response.status_code == 201
        order = response.json()
        assert order["order_number"] == "RST-0001"
        assert order["status"] == "Submitted"
        assert order["lead_time_days"] == max(items["FLT-405"]["lead_time_days"], items["BRG-102"]["lead_time_days"])
        expected_total = 100 * items["FLT-405"]["unit_cost"] + 10 * items["BRG-102"]["unit_cost"]
        assert order["total_value"] == pytest.approx(expected_total)

    def test_unknown_sku_returns_400(self, client):
        response = client.post("/api/restocking/orders", json={"items": [{"sku": "NOPE-000", "quantity": 5}]})
        assert response.status_code == 400

    def test_zero_quantity_returns_400(self, client):
        response = client.post("/api/restocking/orders", json={"items": [{"sku": "FLT-405", "quantity": 0}]})
        assert response.status_code == 400

    def test_empty_order_returns_400(self, client):
        response = client.post("/api/restocking/orders", json={"items": []})
        assert response.status_code == 400

    def test_order_listed_separately_from_client_orders(self, client):
        orders_before = client.get("/api/orders").json()
        summary_before = client.get("/api/dashboard/summary").json()

        client.post("/api/restocking/orders", json={"items": [{"sku": "FLT-405", "quantity": 50}]})

        restock = client.get("/api/restocking/orders").json()
        assert len(restock) == 1
        assert restock[0]["order_number"] == "RST-0001"
        assert client.get("/api/orders").json() == orders_before
        assert client.get("/api/dashboard/summary").json() == summary_before
