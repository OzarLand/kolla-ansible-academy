# LAB callback plugin: writes one JSON line per (task, host) result so that
# executed/skipped/changed tasks and notified handlers can be counted exactly.
from __future__ import absolute_import, division, print_function
__metaclass__ = type
import json, os, time
from ansible.plugins.callback import CallbackBase

DOCUMENTATION = '''
    callback: lab_trace
    type: aggregate
    short_description: lab trace
    description: lab trace
'''

class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'lab_trace'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self):
        super(CallbackModule, self).__init__()
        self.out = open(os.path.join(os.environ['LAB_RUN'], 'trace.jsonl'), 'a')
        self.play = None
        self.start = {}
        self.handler = False

    def v2_playbook_on_play_start(self, play):
        self.play = play.get_name()
        self._w(kind='play', play=self.play)

    def v2_playbook_on_task_start(self, task, is_conditional):
        self.handler = False
        self._w(kind='task_start', play=self.play, task=task.get_name(), action=task.action, tags=sorted(task.tags))

    def v2_playbook_on_handler_task_start(self, task):
        self.handler = True
        self._w(kind='handler_start', play=self.play, task=task.get_name(), action=task.action)

    def v2_runner_on_start(self, host, task):
        self.start[(host.get_name(), task._uuid)] = time.time()

    def _res(self, result, status):
        t = result._task
        h = result._host.get_name()
        r = result._result
        st = self.start.pop((h, t._uuid), None)
        items = r.get('results') if isinstance(r, dict) else None
        self._w(kind='result', play=self.play, task=t.get_name(), role=(t._role.get_name() if t._role else None),
                action=t.action, host=h, status=status, changed=bool(r.get('changed')), handler=self.handler,
                n_items=len(items) if isinstance(items, list) else None,
                n_items_changed=sum(1 for i in items if isinstance(i, dict) and i.get('changed')) if isinstance(items, list) else None,
                dur=round(time.time() - st, 3) if st else None,
                msg=(str(r.get('msg'))[:300] if status == 'failed' else None))

    def v2_runner_on_ok(self, result):
        self._res(result, 'ok')

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._res(result, 'failed_ignored' if ignore_errors else 'failed')

    def v2_runner_on_skipped(self, result):
        self._res(result, 'skipped')

    def v2_runner_on_unreachable(self, result):
        self._res(result, 'unreachable')

    def _w(self, **kw):
        kw['ts'] = round(time.time(), 3)
        self.out.write(json.dumps(kw) + '\n')
        self.out.flush()
