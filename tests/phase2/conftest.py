import os

os.environ["DEBUG"] = "false"
from tests.phase1.test_api import client_factory  # noqa: E402,F401
