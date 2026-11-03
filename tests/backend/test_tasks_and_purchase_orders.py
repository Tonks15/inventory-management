"""
Tests for the tasks and purchase order endpoints.
"""
import pytest

from mock_data import tasks, purchase_orders


@pytest.fixture(autouse=True)
def reset_runtime_state():
    """Tasks and purchase orders live in module-level lists, so restore them around every test."""
    original_pos = list(purchase_orders)
    tasks.clear()
    yield
    tasks.clear()
    purchase_orders[:] = original_pos


def make_task(client, **overrides):
    payload = {"title": "Review stock", "priority": "high", "dueDate": "2025-10-08"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload)


class TestTasksEndpoints:
    """Test suite for task endpoints."""

    def test_get_tasks_empty(self, client):
        """Test getting tasks when none have been created."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_task(self, client):
        """Test creating a task returns a pending task with a generated id."""
        response = make_task(client)
        assert response.status_code == 201

        task = response.json()
        assert task["title"] == "Review stock"
        assert task["priority"] == "high"
        assert task["dueDate"] == "2025-10-08"
        assert task["status"] == "pending"
        # Must not collide with the client's seeded mock tasks (ids 1-4)
        assert task["id"] >= 1000

    def test_get_tasks_newest_first(self, client):
        """Test that tasks are returned newest first."""
        make_task(client, title="first")
        make_task(client, title="second")

        data = client.get("/api/tasks").json()
        assert [t["title"] for t in data] == ["second", "first"]

    def test_create_task_blank_title(self, client):
        """Test that a blank title is rejected."""
        response = make_task(client, title="   ")
        assert response.status_code == 400

    def test_create_task_invalid_priority(self, client):
        """Test that an unknown priority is rejected."""
        response = make_task(client, priority="urgent")
        assert response.status_code == 400

    def test_task_ids_unique_after_delete(self, client):
        """Test that deleting a task never causes an id to be reused."""
        first = make_task(client).json()
        second = make_task(client).json()
        client.delete(f"/api/tasks/{first['id']}")
        third = make_task(client).json()
        assert third["id"] not in (first["id"], second["id"])

    def test_toggle_task(self, client):
        """Test toggling a task back and forth."""
        task = make_task(client).json()

        response = client.patch(f"/api/tasks/{task['id']}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

        response = client.patch(f"/api/tasks/{task['id']}")
        assert response.json()["status"] == "pending"

    def test_delete_task(self, client):
        """Test deleting a task."""
        task = make_task(client).json()

        response = client.delete(f"/api/tasks/{task['id']}")
        assert response.status_code == 200
        assert client.get("/api/tasks").json() == []

    def test_toggle_nonexistent_task(self, client):
        """Test toggling a task that doesn't exist."""
        response = client.patch("/api/tasks/99999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_nonexistent_task(self, client):
        """Test deleting a task that doesn't exist."""
        response = client.delete("/api/tasks/99999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestPurchaseOrderEndpoints:
    """Test suite for purchase order endpoints."""

    @staticmethod
    def po_payload(client, **overrides):
        backlog_id = client.get("/api/backlog").json()[0]["id"]
        payload = {
            "backlog_item_id": backlog_id,
            "supplier_name": "Apex Components Ltd",
            "quantity": 100,
            "unit_cost": 12.5,
            "expected_delivery_date": "2025-11-15",
            "notes": "Rush",
        }
        payload.update(overrides)
        return payload

    def test_create_purchase_order(self, client):
        """Test creating a purchase order for a backlog item."""
        payload = self.po_payload(client)
        response = client.post("/api/purchase-orders", json=payload)
        assert response.status_code == 201

        po = response.json()
        assert po["id"].startswith("PO-")
        assert po["backlog_item_id"] == payload["backlog_item_id"]
        assert po["supplier_name"] == "Apex Components Ltd"
        assert po["quantity"] == 100
        assert po["unit_cost"] == 12.5
        assert po["status"] == "Pending"
        assert "T" in po["created_date"]

    def test_get_purchase_order_by_backlog_item(self, client):
        """Test fetching a purchase order by its backlog item id."""
        payload = self.po_payload(client)
        created = client.post("/api/purchase-orders", json=payload).json()

        response = client.get(f"/api/purchase-orders/{payload['backlog_item_id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_backlog_reflects_purchase_order(self, client):
        """Test that the backlog flags an item once it has a purchase order."""
        payload = self.po_payload(client)
        client.post("/api/purchase-orders", json=payload)

        backlog = client.get("/api/backlog").json()
        flagged = {b["id"]: b["has_purchase_order"] for b in backlog}
        assert flagged[payload["backlog_item_id"]] is True

    def test_create_duplicate_purchase_order(self, client):
        """Test that a backlog item can only have one purchase order."""
        payload = self.po_payload(client)
        client.post("/api/purchase-orders", json=payload)

        response = client.post("/api/purchase-orders", json=payload)
        assert response.status_code == 409

    def test_create_purchase_order_unknown_backlog_item(self, client):
        """Test creating a purchase order for a backlog item that doesn't exist."""
        payload = self.po_payload(client, backlog_item_id="nonexistent-999")
        response = client.post("/api/purchase-orders", json=payload)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.parametrize("field,value", [
        ("quantity", 0),
        ("quantity", -5),
        ("unit_cost", 0),
        ("supplier_name", "  "),
    ])
    def test_create_purchase_order_invalid_input(self, client, field, value):
        """Test that non-positive numbers and blank suppliers are rejected."""
        payload = self.po_payload(client, **{field: value})
        response = client.post("/api/purchase-orders", json=payload)
        assert response.status_code == 400

    def test_get_nonexistent_purchase_order(self, client):
        """Test getting a purchase order that doesn't exist."""
        response = client.get("/api/purchase-orders/nonexistent-999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
