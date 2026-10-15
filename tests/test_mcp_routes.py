from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from sparql_llm.agent.main import app


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/mcp", "/mcp/"])
@pytest.mark.parametrize("scheme", ["http", "https"])
def test_mcp_paths_without_redirects(client: TestClient, path: str, scheme: str) -> None:
    """Both URL spellings must support MCP without a proxy-dependent redirect."""
    headers = {"Accept": "application/json, text/event-stream"}
    url = f"{scheme}://localhost:8000{path}"
    response = client.post(
        url,
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "routing-test", "version": "1.0"},
            },
        },
    )
    assert response.status_code == 200
    assert "location" not in response.headers
    assert "serverInfo" in response.json()["result"]

    response = client.post(
        url,
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    assert response.status_code == 200
    assert "location" not in response.headers
    assert "show_protein_variants" in {tool["name"] for tool in response.json()["result"]["tools"]}
