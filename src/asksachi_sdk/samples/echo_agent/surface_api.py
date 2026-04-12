"""A2A HTTP surface for test-echo (shim — logic lives in echo_agent.py)."""

from .echo_agent import spec

# app is exposed for testing: TestClient(app)
app = spec.build_app()
serve_main = spec.serve_main
