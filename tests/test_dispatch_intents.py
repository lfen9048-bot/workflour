import concurrent.futures
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import dispatch_intents as d


def ident(): return str(uuid.uuid4())


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / '中文项目'
        self.wf = self.root / '.workflour'; self.wf.mkdir(parents=True)
        self.index = self.base / 'private-index'
        self.db = self.base / 'native.db'
        self.owner = {'bot_id': ident(), 'thread_id': ident()}
        self.worker = ident(); self.token = ident(); self.worker_thread = ident()
        self.state = {'workflow': 'plan-code', 'phase': 'implement', 'repair_round': 0,
                      'coordinator_thread': self.owner['thread_id'], 'assignments': {
                          'implement/code-main': {'status': 'claimed', 'bot_id': self.worker, 'dispatch_token': self.token}}}
        self.save_state()
        d.atomic_write(self.wf / 'handoff.json', {'product_surface': 'web'})
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('CREATE TABLE assignments (requester_thread_id TEXT, assignee_thread_id TEXT, assignee_bot_id TEXT, status TEXT, json TEXT)')
        self.add_row({'version': 1, 'id': ident(), 'requester': {'threadId': ident(), 'botId': ident()},
                      'assignee': {'botId': self.owner['bot_id'], 'destination': {'threadId': self.owner['thread_id']}},
                      'status': 'running', 'mode': 'work', 'brief': 'Root task', 'executions': 1, 'createdAt': 1})

    def save_state(self): d.atomic_write(self.wf / 'coordination.json', self.state)

    def add_row(self, row):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute('INSERT INTO assignments VALUES (?,?,?,?,?)', (row['requester']['threadId'],
                      row['assignee']['destination']['threadId'], row['assignee']['botId'], row['status'], json.dumps(row)))

    def prepare(self, phase='implement', role='code-main', **kwargs):
        return d.prepare(self.root, phase, role, '实现已确定的范围，不重做旧任务。', db=self.db, index_home=self.index, **kwargs)

    def row(self, intent, **changes):
        row = {'version': 1, 'id': ident(), 'requester': {'threadId': self.owner['thread_id'], 'botId': self.owner['bot_id']},
               'assignee': {'botId': self.worker, 'destination': {'threadId': self.worker_thread}},
               'status': 'running', 'mode': 'work', 'brief': intent['native_arguments']['message'],
               'executions': 1, 'createdAt': 10}
        row.update(changes)
        return row

    def test_prepare_exact_payload_and_idempotent_preparation(self):
        value = self.prepare()
        self.assertEqual(value['id'], self.prepare()['id'])
        self.assertEqual(d.dispatch_tokens(value['native_arguments']['message']), [self.token])
        self.assertEqual(value['target']['thread'], 'new')
        self.assertEqual(d.preflight(value['native_arguments'], self.owner, index_home=self.index)['ok'], True)
        self.assertEqual(len(list((self.wf / 'dispatch-intents').glob('*.json'))), 1)

    def test_alias_cli_prepares_before_outer_lock_and_real_helper_reads_receipt(self):
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        brief = self.root / 'brief.md'; brief.write_text('CLI 隔离任务，不请求模型。')
        env = {**os.environ, 'WORKFLOUR_NATIVE_DB': str(self.db), 'WORKFLOUR_DISPATCH_HOME': str(self.index)}
        before_ledger = (self.wf / 'coordination.json').read_bytes()
        before_db = self.db.read_bytes()
        command = [sys.executable, str(scripts / 'coordinator-workflow.py'), '--actor', 'plan-lead',
                   '--project', str(self.root), 'prepare-dispatch', 'implement', 'code-main',
                   '--message-file', str(brief), '--title', '编码 · CLI 验证']
        # A second acquisition of coordination.lock would block this process.
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['state'], 'prepared')
        self.assertEqual(value['native_arguments']['bot_ids'], [self.worker])
        self.assertEqual((self.wf / 'coordination.json').read_bytes(), before_ledger)
        self.assertEqual(self.db.read_bytes(), before_db)
        denied = subprocess.run([v if v != 'plan-lead' else 'coordinator' for v in command],
                                env=env, capture_output=True, text=True, timeout=8)
        self.assertNotEqual(denied.returncode, 0)
        self.assertEqual(len(list((self.wf / 'dispatch-intents').glob('*.json'))), 1)
        def helper(action, payload):
            completed = subprocess.run([sys.executable, str(scripts / 'prepare-dispatch.py'), action],
                input=json.dumps(payload), env=env, capture_output=True, text=True, timeout=8)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            return json.loads(completed.stdout)
        helper('preflight', {'arguments': value['native_arguments'], 'binding': self.owner})
        helper('begin', {'arguments': value['native_arguments'], 'binding': self.owner})
        # Simulates the native sender committing its receipt, not a model reply.
        row = self.row(value); self.add_row(row); expected_db = self.db.read_bytes()
        receipt = helper('finish', {'intent_id': value['id'], 'binding': self.owner})
        self.assertEqual((receipt['assignment_id'], receipt['thread_id']), (row['id'], self.worker_thread))
        self.assertEqual(receipt['state'], 'sent')
        self.assertEqual(self.db.read_bytes(), expected_db, 'finish must not write the native database')

    def test_native_unicode_lengths_and_single_line_title_are_checked_before_send(self):
        for kwargs in ({'title': 'x\ny'}, {'title': 'x\u2028y'}, {'title': 'x\ty'},
                       {'title': '😀' * 41}, {'done_when': '😀' * 501}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.prepare(**kwargs)
        with self.assertRaisesRegex(ValueError, '4000'):
            d.prepare(self.root, 'implement', 'code-main', '😀' * 2000, db=self.db, index_home=self.index)
        self.assertFalse(list((self.wf / 'dispatch-intents').glob('*.json')))

    def test_missing_or_handwritten_markers_never_prepare_or_send(self):
        with self.assertRaisesRegex(ValueError, 'handwritten'):
            d.prepare(self.root, 'implement', 'code-main', 'WF-DISPATCH:'+self.token, db=self.db, index_home=self.index)
        with self.assertRaisesRegex(ValueError, 'Missing or ambiguous'):
            d.preflight({'message': 'hello'}, self.owner, index_home=self.index)

    def test_wrong_content_target_thread_and_sender_rejected(self):
        value = self.prepare()
        for field, replacement in [('message', value['native_arguments']['message']+'改'), ('thread', ident()), ('bot_ids', [ident()])]:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'Arguments differ'):
                d.begin({**value['native_arguments'], field: replacement}, self.owner, index_home=self.index)
        with self.assertRaisesRegex(ValueError, 'another native'):
            d.begin(value['native_arguments'], {**self.owner, 'thread_id': ident()}, index_home=self.index)

    def test_claim_change_after_prepare_blocks_before_native_call(self):
        value = self.prepare()
        self.state['assignments']['implement/code-main']['dispatch_token'] = ident(); self.save_state()
        with self.assertRaisesRegex(ValueError, 'Claim or coordinator changed'):
            d.begin(value['native_arguments'], self.owner, index_home=self.index)

    def test_parallel_begin_allows_one_only(self):
        value = self.prepare()
        def start(_):
            try: return d.begin(value['native_arguments'], self.owner, index_home=self.index)['ok']
            except ValueError: return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(sum(pool.map(start, range(4))), 1)
        self.assertEqual(d.locate(value['id'], self.index)[2]['state'], 'sending')

    def test_no_receipt_becomes_uncertain_and_cannot_resend(self):
        value = self.prepare(); d.begin(value['native_arguments'], self.owner, index_home=self.index)
        result = d.finish(value['id'], self.owner, db=self.db, index_home=self.index)
        self.assertEqual(result['state'], 'uncertain')
        with self.assertRaises(ValueError): d.begin(value['native_arguments'], self.owner, index_home=self.index)
        with self.assertRaisesRegex(ValueError, 'uncertain'): self.prepare()
        # A later read can recover a committed receipt without invoking a tool.
        row = self.row(value); self.add_row(row)
        result = d.finish(value['id'], self.owner, db=self.db, index_home=self.index)
        self.assertEqual(result['assignment_id'], row['id'])
        self.assertEqual(result['state'], 'sent')
        self.assertNotIn('uncertainty', result)
        with self.assertRaises(ValueError): d.begin(value['native_arguments'], self.owner, index_home=self.index)

    def test_conflicting_receipts_remain_uncertain(self):
        value = self.prepare(); d.begin(value['native_arguments'], self.owner, index_home=self.index)
        self.add_row(self.row(value)); self.add_row(self.row(value))
        self.assertEqual(d.finish(value['id'], self.owner, db=self.db, index_home=self.index)['state'], 'uncertain')

    def test_capability_contract_cannot_be_silently_downgraded(self):
        value = self.prepare(require_image=True)
        d.begin(value['native_arguments'], self.owner, index_home=self.index)
        self.add_row(self.row(value))
        receiver = {'bot_id': self.worker, 'thread_id': self.worker_thread}
        self.assertEqual(d.requirements_for_binding(receiver, db=self.db, index_home=self.index)['required_capabilities'], ['image'])
        path = self.wf / 'dispatch-intents' / (value['id'] + '.json')
        damaged = d.read_json(path); damaged['required_capabilities'] = []
        d.atomic_write(path, damaged)
        with self.assertRaisesRegex(ValueError, 'contract changed'):
            d.requirements_for_binding(receiver, db=self.db, index_home=self.index)
        # Even recalculating every local checksum cannot rewrite the native
        # assignment's already-committed contract/brief.
        damaged['request_sha256'] = d.digest({key: damaged[key] for key in d.BASIS_KEYS})
        damaged['native_arguments']['message'] = d.sealed_message(damaged['primary_token'], damaged['id'], damaged['request_sha256'], damaged['message'])
        damaged['payload_sha256'] = d.digest(damaged['native_arguments'])
        d.atomic_write(path, damaged)
        with self.assertRaisesRegex(ValueError, 'unconfirmed'):
            d.requirements_for_binding(receiver, db=self.db, index_home=self.index)

    def test_native_receipt_must_preserve_exact_prepared_brief(self):
        value = self.prepare(); d.begin(value['native_arguments'], self.owner, index_home=self.index)
        self.add_row(self.row(value, brief=value['native_arguments']['message']+' additional unprepared work'))
        self.assertEqual(d.finish(value['id'], self.owner, db=self.db, index_home=self.index)['state'], 'uncertain')

    def test_web_experience_requires_image_cli_does_not(self):
        self.state.update(phase='experience', assignments={'experience/plan-review': {'status': 'claimed', 'bot_id': self.worker, 'dispatch_token': self.token}})
        self.save_state()
        value = self.prepare('experience', 'plan-review')
        self.assertEqual(value['required_capabilities'], ['image'])
        self.assertTrue(value['native_arguments']['rework'])
        self.assertEqual(value['native_arguments']['thread'], 'new')
        self.state['repair_round'] = 1
        self.state['assignments']['experience/plan-review@1'] = {'status': 'claimed', 'bot_id': self.worker, 'dispatch_token': ident()}
        self.save_state(); d.atomic_write(self.wf / 'handoff.json', {'product_surface': 'cli'})
        self.assertEqual(self.prepare('experience', 'plan-review')['required_capabilities'], [])

    def test_receiver_finds_sending_intent_before_sender_result(self):
        value = self.prepare(require_image=True)
        d.begin(value['native_arguments'], self.owner, index_home=self.index)
        self.add_row(self.row(value))
        bound = {'bot_id': self.worker, 'thread_id': self.worker_thread}
        self.assertEqual(d.requirements_for_binding(bound, db=self.db, index_home=self.index),
                         {'required_capabilities': ['image'], 'intents': [value['id']]})
        with self.assertRaisesRegex(ValueError, 'receiver identity'):
            d.requirements_for_binding({**bound, 'bot_id': ident()}, db=self.db, index_home=self.index)

    def test_receiver_does_not_lose_image_on_uncertain_receipt(self):
        value = self.prepare(require_image=True)
        d.begin(value['native_arguments'], self.owner, index_home=self.index)
        d.finish(value['id'], self.owner, db=self.db, index_home=self.index)
        self.add_row(self.row(value))
        with self.assertRaisesRegex(ValueError, 'capabilities are unconfirmed'):
            d.requirements_for_binding({'bot_id': self.worker, 'thread_id': self.worker_thread}, db=self.db, index_home=self.index)

    def test_historical_task_does_not_gain_capabilities_from_prompt_words(self):
        value = self.prepare()
        self.add_row(self.row(value, brief='需要截图 image required'))
        self.assertEqual(d.requirements_for_binding({'bot_id': self.worker, 'thread_id': self.worker_thread}, db=self.db, index_home=self.index),
                         {'required_capabilities': [], 'intents': []})

    def test_supplement_retains_target_token_and_requires_unchanged_scope(self):
        value = self.prepare(); d.begin(value['native_arguments'], self.owner, index_home=self.index)
        primary = self.row(value); self.add_row(primary)
        d.finish(value['id'], self.owner, db=self.db, index_home=self.index)
        self.state['assignments']['implement/code-main'].update(status='running', assignment_id=primary['id'], thread_id=self.worker_thread)
        self.save_state()
        evidence = self.root / 'scope.md'; evidence.write_text('只补当前测试，不重复主任务。')
        extra = self.prepare(supplement=True, reason='补测', evidence='scope.md')
        self.assertEqual(extra['primary_token'], value['primary_token'])
        self.assertEqual(extra['target']['thread'], self.worker_thread)
        self.assertNotEqual(extra['id'], value['id'])
        evidence.write_text('改了范围')
        with self.assertRaisesRegex(ValueError, 'scope changed'):
            d.begin(extra['native_arguments'], self.owner, index_home=self.index)

    def test_symlink_intent_rejected(self):
        value = self.prepare(); path = self.wf / 'dispatch-intents' / (value['id']+'.json')
        target = self.base / 'outside.json'; path.rename(target); path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            d.preflight(value['native_arguments'], self.owner, index_home=self.index)


if __name__ == '__main__': unittest.main()
