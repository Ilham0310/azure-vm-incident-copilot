"""
SOP KB initializer with SSL bypass for corporate networks.

Usage: python setup/init_sop_kb_offline.py
"""
import os
import sys

# Bypass SSL verification for corporate proxy/firewall
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

# Monkey-patch httpx to disable SSL verification
import httpx
_OrigClient = httpx.Client
class _NoSSLClient(_OrigClient):
    def __init__(self, *a, **kw):
        kw['verify'] = False
        super().__init__(*a, **kw)
httpx.Client = _NoSSLClient

# Now run the real initializer
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from setup.initialize_sop_kb import main

if __name__ == '__main__':
    main()
