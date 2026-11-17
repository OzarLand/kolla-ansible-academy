# e3 callback: append every kolla_docker / command result, unabridged (invocation.module_args included), as one
# JSON line to $E3_RECORD. Display is left to the default callback. A loop task is recorded once, with its 'results'.
from __future__ import absolute_import, division, print_function
__metaclass__ = type
import json
import os

from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'e3_record'
    CALLBACK_NEEDS_WHITELIST = True

    def _rec(self, status, result):
        if result._task.action not in ('kolla_docker', 'command'):
            return
        path = os.environ.get('E3_RECORD')
        if not path:
            return
        with open(path, 'a') as f:
            f.write(json.dumps({'task': result._task.get_name(), 'status': status, 'result': result._result},
                               default=str) + '\n')

    def v2_runner_on_ok(self, result):
        self._rec('ok', result)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._rec('failed', result)

    def v2_runner_on_skipped(self, result):
        self._rec('skipped', result)
