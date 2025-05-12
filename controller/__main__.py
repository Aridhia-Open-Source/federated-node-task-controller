"""
Entrypoint for the FNTC
"""

from .controller import start

print("Starting the controller")

if __name__ == "__main__":
    while True:
        start()
