"""
Simple override of certain requests args.
    - if the `DEVELOPMENT` env var is set, it will ignore SSL
    - it also sets a global timeout to be 60 seconds
"""

import functools
import requests

from controller.const import LOCAL_DEV

client = requests.Session()
client.request = functools.partial(client.request, timeout=60)
if LOCAL_DEV:
    client.verify = False
