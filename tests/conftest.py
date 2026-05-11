"""
Global pytest configuration.

Patches SSL verification for corporate networks where HuggingFace
downloads fail due to SSL certificate issues.
"""
import os
import httpx

# Disable SSL verification for HuggingFace model downloads
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

_OrigClient = httpx.Client
class _NoSSLClient(_OrigClient):
    def __init__(self, *a, **kw):
        kw['verify'] = False
        super().__init__(*a, **kw)
httpx.Client = _NoSSLClient
