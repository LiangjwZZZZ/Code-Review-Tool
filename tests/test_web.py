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


def test_analyze_sse_endpoint():
    """Test SSE analysis endpoint returns event stream."""
    from fastapi.testclient import TestClient
    from review.web.server import app
    from unittest.mock import patch, MagicMock

    client = TestClient(app)

    mock_report = MagicMock()
    mock_report.risk_level = "LOW"
    mock_report.commit_hash = "abc123"

    with patch('review.engine.report_generator.generate_report', return_value=mock_report), \
         patch('review.store.report_store.save_report'):
        response = client.get(
            "/api/analyze-sse",
            params={"commit": "abc123", "repo": "."}
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
