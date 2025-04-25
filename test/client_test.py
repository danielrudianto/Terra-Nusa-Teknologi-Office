import pytest
from httpx import AsyncClient
from main import app  # Import your FastAPI app

@pytest.mark.asyncio
async def test_create_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/clients/",
            json={
                "name": "John Doe",
                "address": "123 Main St",
                "phone_number": "1234567890",
                "email": "john.doe@example.com",
                "secondary_email": None,
                "npwp": None,
            },
        )
    assert response.status_code == 200
    assert response.json()["message"] == "Client created successfully"

@pytest.mark.asyncio
async def test_get_all_clients():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/clients/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_get_client_by_id():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Assuming client with ID 1 exists
        response = await client.get("/clients/1")
    if response.status_code == 404:
        assert response.json()["detail"]["error"] == "Client not found"
    else:
        assert response.status_code == 200
        assert "name" in response.json()

@pytest.mark.asyncio
async def test_update_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/clients/1",
            json={
                "name": "Jane Doe",
                "address": "456 Elm St",
                "phone_number": "9876543210",
                "email": "jane.doe@example.com",
                "secondary_email": None,
                "npwp": None,
            },
        )
    if response.status_code == 404:
        assert response.json()["detail"]["error"] == "Client not found"
    else:
        assert response.status_code == 200
        assert response.json()["message"] == "Client updated successfully"

@pytest.mark.asyncio
async def test_delete_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.delete("/clients/1")
    if response.status_code == 404:
        assert response.json()["detail"]["error"] == "Client not found"
    else:
        assert response.status_code == 200
        assert response.json()["message"] == "Client deleted successfully"