from fastapi.testclient import TestClient

from api.main import app
from api.routes import dashboard


def test_dashboard_summary_returns_empty_when_supabase_unconfigured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    response = TestClient(app).get("/dashboard/summary")

    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "document_count": 0,
        "county_count": 0,
        "latest_year": None,
        "years": [],
        "counties": [],
    }


def test_dashboard_summary_groups_documents_by_county(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    monkeypatch.setattr(
        dashboard,
        "_supabase_select",
        lambda params: [
            {
                "id": "1",
                "title": "Kisumu Budget",
                "county": "Kisumu",
                "financial_year": "2023/24",
                "document_type": "county_budget",
                "source_file": "kisumu.md",
                "sectors": ["health", "roads"],
                "ingested_at": "2026-01-01T00:00:00Z",
            },
            {
                "id": "2",
                "title": "Nairobi Budget",
                "county": "Nairobi",
                "financial_year": "2024/25",
                "document_type": "county_budget",
                "source_file": "nairobi.md",
                "sectors": ["education"],
                "ingested_at": "2026-01-02T00:00:00Z",
            },
        ],
    )

    response = TestClient(app).get("/dashboard/summary")

    body = response.json()
    assert response.status_code == 200
    assert body["configured"] is True
    assert body["document_count"] == 2
    assert body["county_count"] == 2
    assert body["latest_year"] == "2024/25"
    assert body["counties"][0]["county"] == "Kisumu"


def test_dashboard_search_returns_snippets(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    monkeypatch.setattr(
        dashboard,
        "_supabase_select",
        lambda params: [
            {
                "id": "1",
                "title": "Kisumu Budget",
                "county": "Kisumu",
                "financial_year": "2023/24",
                "source_file": "kisumu.md",
                "sectors": ["roads"],
                "content": "The roads allocation is Ksh 800,000,000 for the year.",
            }
        ],
    )

    response = TestClient(app).get("/dashboard/search", params={"q": "roads"})

    body = response.json()
    assert response.status_code == 200
    assert body["configured"] is True
    assert body["results"][0]["county"] == "Kisumu"
    assert "roads allocation" in body["results"][0]["snippet"]
