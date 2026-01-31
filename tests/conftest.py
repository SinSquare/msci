"""conftest"""

import pytest
from fastapi.testclient import TestClient

from msci.main import app

pytest_plugins = "fw_http_testserver"


@pytest.fixture(scope="function")
def client():
    return TestClient(app)
