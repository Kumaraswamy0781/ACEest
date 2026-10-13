"""Verify a running image serves health and program endpoints after startup."""
import json
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


def check(base_url):
    deadline = time.monotonic() + 30
    while True:
        try:
            with urlopen(f'{base_url}/health', timeout=2) as response:
                health = json.load(response)
            if health.get('status') != 'ok' or health.get('version') != '3.2.4':
                raise RuntimeError(f'Unexpected health response: {health}')
            break
        except (URLError, TimeoutError, ConnectionError) as error:
            if time.monotonic() >= deadline:
                raise RuntimeError('The container did not become healthy within 30 seconds.') from error
            time.sleep(1)
    with urlopen(f'{base_url}/api/programs', timeout=5) as response:
        programs = json.load(response)
    if set(programs) != {'Fat Loss', 'Muscle Gain', 'Beginner'}:
        raise RuntimeError(f'Unexpected program response: {programs}')
    print('Container startup, health, and program endpoints passed.')


if __name__ == '__main__':
    check(sys.argv[1].rstrip('/'))
