"""Check Honcho extraction with an isolated fictional user, then remove the test workspace."""

import argparse
import json
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path


def verify(base, timeout):
    workspace = 'shopping-model-test-' + uuid.uuid4().hex[:12]
    report = {'workspace': workspace, 'fictional_test_data': True, 'passed': False}

    def request(path, body=None, method=None):
        req = urllib.request.Request(base.rstrip('/') + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else None

    path = '/v3/workspaces/' + workspace
    created = False
    sessions = []
    start = time.monotonic()
    try:
        request('/v3/workspaces', {'id': workspace})
        created = True
        request(path + '/peers', {'id': 'fictional-user'})
        request(path + '/sessions', {'id': 'first-session',
            'peers': {'fictional-user': {'observe_me': True}}})
        sessions.append('first-session')
        request(path + '/sessions/first-session/messages', {'messages': [{
            'peer_id': 'fictional-user',
            'content': 'Dies sind fiktive Testdaten: Ich interessiere mich fuer Smart Home und Technik. '
                       'Mein Shopping-Budget ist genau CHF 149. Ich lehne zwingende Cloud-Abos ab.',
        }]})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            context = request(path + '/peers/fictional-user/context')
            text = json.dumps(context, ensure_ascii=False).lower()
            if '149' in text and 'smart' in text:
                # A fresh session retrieves the same peer, without repeating the preferences.
                request(path + '/sessions', {'id': 'second-session',
                    'peers': {'fictional-user': {'observe_me': True}}})
                sessions.append('second-session')
                second = request(path + '/peers/fictional-user/context')
                report['context_from_second_session'] = second
                report['passed'] = '149' in json.dumps(second) and 'smart' in json.dumps(second).lower()
                break
            time.sleep(5)
        report['queue'] = request(path + '/queue/status')
        report['seconds'] = round(time.monotonic() - start, 2)
    finally:
        if created:
            for session in sessions:
                request(path + '/sessions/' + session, method='DELETE')
            for attempt in range(10):
                try:
                    request(path, method='DELETE')
                    report['test_workspace_cleanup_requested'] = True
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code != 409 or attempt == 9:
                        raise
                    time.sleep(1)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://honcho:8000')
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(args.base_url, args.timeout)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True, indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
