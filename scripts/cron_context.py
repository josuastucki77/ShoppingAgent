"""Read-only Honcho context for Hermes cron (the Honcho plugin skips cron)."""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def collect(home):
    config = json.loads((home / 'honcho.json').read_text(encoding='utf-8'))
    base = config['baseUrl'].rstrip('/')
    workspace = urllib.parse.quote(config['workspace'], safe='')
    peer = urllib.parse.quote(config['peerName'], safe='')
    request = urllib.request.Request(f'{base}/v3/workspaces/{workspace}/peers/{peer}/context')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            context = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        # A new user has no peer yet. Confirm the API is up before using defaults.
        with urllib.request.urlopen(base + '/health', timeout=10) as response:
            response.read()
        context = {'empty_profile': True}
    cutoff = datetime.now().timestamp() - timedelta(days=30).total_seconds()
    previous_urls = set()
    for report in (home / 'cron' / 'output').glob('*/*.md'):
        if report.stat().st_mtime < cutoff:
            continue
        body = report.read_text(encoding='utf-8').split('## Response', 1)
        if len(body) == 2:
            previous_urls.update(re.findall(r'https://www\.galaxus\.ch/[^\s<>\)\]\"?]+', body[1]))
    try:
        zone = ZoneInfo(os.getenv('TZ', 'Europe/Zurich'))
    except ZoneInfoNotFoundError:
        # Windows Python need not have IANA data; an explicit UTC offset stays accurate.
        zone = timezone.utc
    return {
        'source': 'Local Honcho API (read-only; cron plugin intentionally disabled)',
        'execution_time': datetime.now(zone).isoformat(),
        'honcho_context': context,
        'previous_product_urls_30_days': sorted(previous_urls),
    }


if __name__ == '__main__':
    # Errors fail the prep script instead of disguising an outage as an empty profile.
    result = collect(Path(os.getenv('HERMES_HOME', '/opt/data')))
    print(json.dumps(result, ensure_ascii=False, indent=2))
