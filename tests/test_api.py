import pytest
import os
from fastapi.testclient import TestClient
from unittest import mock
from msci.main import app


EXTRACT_TEXTS = {
    "title1": (
        "Lorem Ipsum is simply dummy text of the printing and typesetting industry. "
        "Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, "
        "when an unknown printer took a galley of type and scrambled it to make a type"
        " specimen book. It has survived not only five centuries, but also the leap "
        "into electronic typesetting, remaining essentially unchanged"
    ),
    "title2": "title2",
    "title3": "title3",
}
LINKS_RESPONSE = {
    "query": {"pages": {"1": {"links": [{"title": "title2"}, {"title": "title3"}]}}}
}
EXTRACT_RESPONSE = {"query": {"pages": {"1": {"title": "title", "extract": ""}}}}


@pytest.fixture
def env(http_testserver):
    env = {"MSCI_WIKI_API_URL": http_testserver.url}
    with mock.patch.dict(os.environ, env):
        yield env


@pytest.fixture
def server(http_testserver):
    def callback():
        req = http_testserver.request
        titles = req.args.get("titles").split("|")
        if titles == ["error"]:
            return {}, 500
        prop = req.args.get("prop")
        if prop == "links":
            return LINKS_RESPONSE
        resp = {}
        for i, t in enumerate(titles):
            resp[i] = {"title": t, "extract": EXTRACT_TEXTS.get(t, "n/a")}
        return {"query": {"pages": resp}}

    http_testserver.add_callback("/", callback)


def test_api_get(env, server):
    client = TestClient(app)
    resp = client.get("/word-frequency", params={"article": "title1", "depth": 0})
    assert resp.status_code == 200
    words = set(resp.json().keys())
    assert "title2" not in words

    resp = client.get("/word-frequency", params={"article": "title1", "depth": 1})
    assert resp.status_code == 200
    words = set(resp.json().keys())
    assert "title2" in words
    assert "title3" in words


def test_api_post(env, server):
    client = TestClient(app)
    resp = client.post("/keywords", json={"article": "title1", "depth": 0})
    assert resp.status_code == 200
    words = set(resp.json().keys())
    assert "title2" not in words

    resp = client.post("/keywords", json={"article": "title1", "depth": 1})
    assert resp.status_code == 200
    words = set(resp.json().keys())
    assert "title2" in words
    assert "title3" in words

    resp = client.post(
        "/keywords", json={"article": "title1", "depth": 1, "ignore_list": ["title2"]}
    )
    assert resp.status_code == 200
    words = set(resp.json().keys())
    assert "title2" not in words
    assert "title3" in words

    resp = client.post(
        "/keywords", json={"article": "title1", "depth": 1, "percentile": 95}
    )
    assert resp.status_code == 200
    words = set(resp.json().keys())
    assert "Lorem" not in words
    assert "title3" in words


def test_api_get_error(env, server):
    client = TestClient(app)
    resp = client.get("/word-frequency", params={"article": "error", "depth": 0})
    assert resp.status_code == 500
    assert resp.json() == {"detail": {"message": "An unknown error happened"}}


def test_api_real():
    client = TestClient(app)
    resp = client.get("/word-frequency", params={"article": "test", "depth": 0})
    assert resp.status_code == 200
    assert len(resp.json().values()) > 100
    assert "test" in resp.json()
