"""Real Python CLI/Node integration with an isolated native SQLite fixture."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import dispatch_intents as dispatch


class CapabilityDispatchIntegration(unittest.TestCase):
    def test_node_receiver_reads_only_native_bound_assignment(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); project = base / 'project'; wf = project / '.workflour'; wf.mkdir(parents=True)
            db = base / 'native.sqlite'; index = base / 'index'; dsh = base / 'dsh'
            uid = lambda: str(uuid.uuid4())
            owner = {'bot_id': uid(), 'thread_id': uid()}; receiver = {'bot_id': uid(), 'thread_id': uid()}
            token = uid()
            dispatch.atomic_write(wf / 'coordination.json', {'workflow': 'plan-code', 'phase': 'experience', 'repair_round': 0,
                'coordinator_thread': owner['thread_id'], 'assignments': {'experience/plan-review': {
                    'status': 'claimed', 'bot_id': receiver['bot_id'], 'dispatch_token': token}}})
            dispatch.atomic_write(wf / 'handoff.json', {'product_surface': 'web'})
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute('CREATE TABLE assignments (requester_thread_id TEXT, assignee_thread_id TEXT, assignee_bot_id TEXT, status TEXT, json TEXT)')
                root = {'version': 1, 'id': uid(), 'requester': {'threadId': uid(), 'botId': uid()},
                    'assignee': {'botId': owner['bot_id'], 'destination': {'threadId': owner['thread_id']}},
                    'status': 'running', 'mode': 'work', 'brief': 'root task', 'executions': 1, 'createdAt': 1}
                conn.execute('INSERT INTO assignments VALUES (?,?,?,?,?)', (root['requester']['threadId'], owner['thread_id'], owner['bot_id'], 'running', json.dumps(root)))
            intent = dispatch.prepare(project, 'experience', 'plan-review', '真实体验验收', db=db, index_home=index)
            dispatch.begin(intent['native_arguments'], owner, index_home=index)
            row = {'version': 1, 'id': uid(), 'requester': {'threadId': owner['thread_id'], 'botId': owner['bot_id']},
                'assignee': {'botId': receiver['bot_id'], 'destination': {'threadId': receiver['thread_id']}},
                'status': 'running', 'mode': 'work', 'brief': intent['native_arguments']['message'], 'executions': 1, 'createdAt': 2}
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute('INSERT INTO assignments VALUES (?,?,?,?,?)', (owner['thread_id'], receiver['thread_id'], receiver['bot_id'], 'running', json.dumps(row)))
            binding = dsh / 'workflour-session-bindings/session-one.json'; binding.parent.mkdir(parents=True)
            binding.write_text(json.dumps({'schema_version': 1, 'session_id': 'session-one', **receiver}))
            env = {**os.environ, 'DSH_HOME': str(dsh), 'WORKFLOUR_NATIVE_DB': str(db), 'WORKFLOUR_DISPATCH_HOME': str(index)}
            code = "import {createTaskCapabilities} from './integrations/openmausbot/model-fallback/task-capabilities.mjs'; console.log(JSON.stringify(await createTaskCapabilities().requirements('session-one')));"
            result = subprocess.run(['node', '--input-type=module', '-e', code], cwd=ROOT, env=env, text=True, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {'required_capabilities': ['image'], 'intents': [intent['id']]})
            # A different real thread cannot inherit requirements from text/cwd.
            binding.write_text(json.dumps({'schema_version': 1, 'session_id': 'session-one', 'bot_id': receiver['bot_id'], 'thread_id': uid()}))
            result = subprocess.run(['node', '--input-type=module', '-e', code], cwd=ROOT, env=env, text=True, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['required_capabilities'], [])


if __name__ == '__main__':
    unittest.main()
