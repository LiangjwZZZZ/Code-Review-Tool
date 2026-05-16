from fastapi.testclient import TestClient
from review.web.server import app

client = TestClient(app)


def test_api_list_reports():
    response = client.get("/api/reports")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_get_report_not_found():
    response = client.get("/api/reports/nonexistent")
    assert response.status_code == 404


def test_api_get_report_format_not_found():
    response = client.get("/api/reports/nonexistent/format")
    assert response.status_code == 404
