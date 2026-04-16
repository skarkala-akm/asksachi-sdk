from __future__ import annotations

from fastapi.testclient import TestClient

from my_agent.agent import app


def test_agent_card_and_message_send() -> None:
    c = TestClient(app)
    r = c.get('/.well-known/agent-card.json')
    assert r.status_code == 200
    r2 = c.post('/message:send', json={'message': {'parts': [{'text': 'ping'}]}})
    assert r2.status_code == 200
    assert r2.json()['task']['status']['state'] == 'TASK_STATE_COMPLETED'
