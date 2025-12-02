"""
Entrypoint for the FNTC
"""
import asyncio
from .controller import start

print("Starting the controller")

if __name__ == "__main__":
    while True:
        asyncio.run(start())
