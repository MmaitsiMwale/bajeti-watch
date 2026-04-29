from agent import graph
from agent.nodes.intake import intake_node


def test_intake_extracts_county_and_sector_query():
    state = {
        "raw_message": "Kisumu health budget 2023/24",
        "channel": "whatsapp",
        "query": "",
        "county_hint": None,
        "year_hint": None,
        "query_type": "general",
        "chunks": [],
        "llm_response": "",
        "final_reply": "",
    }

    result = intake_node(state)

    assert result["query"] == "Kisumu health budget 2023/24"
    assert result["county_hint"] == "Kisumu"
    assert result["year_hint"] == "2023/24"
    assert result["query_type"] == "sector_query"


def test_graph_runs_with_mocked_external_nodes(monkeypatch):
    def fake_retrieval(state):
        return {
            **state,
            "chunks": [
                {
                    "content": "Roads allocation: Ksh 800,000,000",
                    "metadata": {
                        "county": "Kisumu",
                        "financial_year": "2023/24",
                        "source_file": "kisumu_budget.md",
                    },
                    "similarity": 0.92,
                }
            ],
        }

    def fake_summarizer(state):
        return {
            **state,
            "llm_response": "Kisumu allocated Ksh 800,000,000 to roads.",
        }

    monkeypatch.setattr(graph, "retrieval_node", fake_retrieval)
    monkeypatch.setattr(graph, "summarizer_node", fake_summarizer)

    app = graph.build_graph()
    result = app.invoke(
        {
            "raw_message": "Kisumu roads",
            "channel": "whatsapp",
            "query": "",
            "county_hint": None,
            "year_hint": None,
            "query_type": "general",
            "chunks": [],
            "llm_response": "",
            "final_reply": "",
        }
    )

    assert "Ksh 800,000,000" in result["final_reply"]
    assert "Bajeti Watch" in result["final_reply"]


def test_run_agent_uses_compiled_graph(monkeypatch):
    class FakeGraph:
        def invoke(self, state):
            assert state["raw_message"] == "Nairobi"
            assert state["channel"] == "whatsapp"
            return {"final_reply": "Nairobi budget summary"}

    monkeypatch.setattr(graph, "_graph", FakeGraph())

    assert graph.run_agent("Nairobi") == "Nairobi budget summary"
