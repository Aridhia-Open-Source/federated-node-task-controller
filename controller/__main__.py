"""
Entrypoint for the FNTC
"""
from urllib3.exceptions import ProtocolError
from .controller import start

print("Starting the controller")

if __name__ == "__main__":
    try:
        start()
    except ProtocolError:
        print("Connection expired. Reconnecting...")
        start()
