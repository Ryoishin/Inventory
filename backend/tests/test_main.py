from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

def test_health_is_live():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_local_frontend_origins_are_allowed():
    response = client.options("/api/chat", headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"

def test_sql_playground_returns_documented_sample_data():
    response = client.post("/api/sql", json={"query": "SELECT name, price FROM sample_products ORDER BY price DESC LIMIT 2"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"] == "fictional SQL practice data"
    assert payload["row_count"] == 2
    assert payload["rows"][0]["name"] == "Desk lamp"

def test_sql_playground_rejects_mutations():
    response = client.post("/api/sql", json={"query": "DELETE FROM sample_products"})
    assert response.status_code == 400

def test_sql_playground_restricts_tables():
    response = client.post("/api/sql", json={"query": "SELECT * FROM sqlite_master"})
    assert response.status_code == 400

def test_sql_playground_rejects_extension_loading():
    response = client.post("/api/sql", json={"query": "SELECT load_extension('unused')"})
    assert response.status_code == 400

def test_safe_lookup_treats_input_as_data():
    response = client.get("/api/security/lookup", params={"term": "' OR 1=1 --"})
    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert "Parameterized SQL" in response.json()["query_style"]

def test_ai_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Tell me about the portfolio"}]})
    assert response.status_code == 503

def test_quality_dashboard_does_not_claim_a_ci_run_without_configuration(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "")
    response = client.get("/api/quality")
    assert response.status_code == 200
    assert response.json()["status"] == "not_configured"
