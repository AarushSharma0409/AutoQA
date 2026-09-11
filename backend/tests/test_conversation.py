import asyncio

from app.db import Session, Task
from app.main import app, identity
from app.runtime import run_task
from app.provider import prepare_call


def test_follow_up_reuses_upload_and_preserves_versions(client):
    upload = client.post('/api/uploads', files={'file': ('sales.csv', b'category,revenue\nA,10\nB,20\n')}).json()
    task = client.post('/api/tasks', json={'goal': 'Analyze and report', 'file_ids': [upload['id']]}).json()
    asyncio.run(run_task(task['id']))
    old = client.get('/api/tasks/' + task['id']).json()
    assert old['status'] == 'completed'
    old_report = next(f for f in old['files'] if f['name'] == 'report.md')
    content = client.get('/api/files/' + old_report['id']).content
    path = '/api/tasks/' + task['id'] + '/messages'
    assert client.post(path, json={'goal': 'Create another report from the same CSV'}).status_code == 200
    assert client.post(path, json={'goal': 'Duplicate submission'}).status_code == 409
    asyncio.run(run_task(task['id']))
    new = client.get('/api/tasks/' + task['id']).json()
    assert new['status'] == 'completed'
    assert len(new['turns']) == 1
    assert old_report['id'] in new['turns'][0]['file_ids']
    assert new['current_file_ids'] and old_report['id'] not in new['current_file_ids']
    assert client.get('/api/files/' + old_report['id']).content == content
    assert sum(f['kind'] == 'upload' for f in new['files']) == 1
    assert len(client.get('/api/tasks').json()) == 1
    with Session() as db:
        saved = db.get(Task, task['id'])
        request, _ = prepare_call('Revise report', saved.checkpoint, [])
        assert 'Analyze and report' in request['messages'][1]['content']
    assert client.post(path, json={'goal': 'One more version'}).status_code == 200
    assert len(client.get('/api/tasks/' + task['id']).json()['turns']) == 2


def test_follow_up_ownership_and_approval_reset(client):
    task = client.post('/api/tasks', json={'goal': 'Original request'}).json()
    with Session.begin() as db:
        row = db.get(Task, task['id'])
        row.status = 'canceled'
        row.checkpoint = {'approval': {'approved': False}, 'pending': {'tool': 'python'}, 'tokens': 30000}
    path = '/api/tasks/' + task['id'] + '/messages'
    app.dependency_overrides[identity] = lambda: 'another-user'
    try:
        assert client.post(path, json={'goal': 'Try taking over'}).status_code == 404
    finally:
        app.dependency_overrides.clear()
    assert client.post(path, json={'goal': 'Revised safe request'}).status_code == 200
    with Session() as db:
        cp = db.get(Task, task['id']).checkpoint
        assert 'approval' not in cp and 'pending' not in cp and 'tokens' not in cp
        assert cp['turns'][0]['usage']['tokens'] == 30000
