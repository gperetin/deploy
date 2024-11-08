import time
import subprocess

import requests


def test_deploys_a_demo_service():
    ret = subprocess.call('uv run --with "fabric" --with "gitpython" deploy.py', shell=True)
    assert ret == 0

    time.sleep(1) # Give it some time for the process to become ready
    r = requests.get("http://bourne:8085")
    assert "Hello" in r.json()
