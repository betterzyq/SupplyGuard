import os

os.environ["DEBUG"] = "false"
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
from tests.phase1.test_api import client_factory  # noqa: E402,F401
