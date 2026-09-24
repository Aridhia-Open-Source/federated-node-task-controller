"""
Test-side helper for the azcopy integration test, run in its own container next to Azurite.

    azurite_helper.py sas <container>          prints a container URL with a write SAS
    azurite_helper.py read <container> <blob>  prints the blob's content
"""
import sys
from datetime import datetime, timedelta, timezone

from azure.storage.blob import BlobServiceClient, ContainerSasPermissions, generate_container_sas

# Azurite's well-known development account. Not a secret.
ACCOUNT = "devstoreaccount1"
KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
# Production-style host (account as the first label), so azcopy parses the URL the way it
# does a real storage account and needs no --from-to hint.
URL = f"http://{ACCOUNT}.blob.azurite:10000"


def client() -> BlobServiceClient:
    return BlobServiceClient.from_connection_string(
        f"DefaultEndpointsProtocol=http;AccountName={ACCOUNT};AccountKey={KEY};BlobEndpoint={URL};"
    )


def sas(container: str):
    client().create_container(container)
    token = generate_container_sas(
        ACCOUNT, container, account_key=KEY,
        permission=ContainerSasPermissions(read=True, write=True, create=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    print(f"{URL}/{container}?{token}")


def read(container: str, blob: str):
    data = client().get_container_client(container).get_blob_client(blob).download_blob().readall()
    sys.stdout.write(data.decode())


if __name__ == "__main__":
    {"sas": sas, "read": read}[sys.argv[1]](*sys.argv[2:])
