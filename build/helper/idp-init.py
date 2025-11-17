import os
import requests
import sys

KEYCLOAK_URL = os.getenv('KC_HOST')
KEYCLOAK_PASS = os.getenv('KEYCLOAK_ADMIN_PASSWORD')
GITHUB_SECRET = os.getenv('GITHUB_SECRET')
GITHUB_CLIENTID = os.getenv('GITHUB_CLIENTID')
REPOSITORY = os.getenv('REPOSITORY')

if not REPOSITORY:
    print("REPOSITORY name missing. Skipping IdP setup")
    sys.exit(1)

# Ready check on backend
for i in range(10):
  hc_resp = requests.get(f"{KEYCLOAK_URL}/realms/FederatedNode")
  if hc_resp.ok:
    break

  time.sleep(10)

# Login as admin
admin_response = requests.post(
    f"{KEYCLOAK_URL}/realms/FederatedNode/protocol/openid-connect/token",
    headers={
        'Content-Type': 'application/x-www-form-urlencoded'
    },
    data={
        'grant_type':'password',
        'scope':'openid',
        'username':'admin',
        'password': KEYCLOAK_PASS,
        'client_id':'admin-cli'
    }
)

if not admin_response.ok:
    print(admin_response.json())
    exit(1)

print("Logged in!")
admin_token = admin_response.json()["access_token"]

idp_alias = REPOSITORY.replace("/", "-")

# Create IdP entry
idp_create_response = requests.post(
    f"{KEYCLOAK_URL}/admin/realms/FederatedNode/identity-provider/instances",
    json={
        "config": {
            "clientId": GITHUB_CLIENTID,
            "clientSecret": GITHUB_SECRET,
            "guiOrder":"",
            "baseUrl":"",
            "apiUrl":""
        },
        "providerId": "github",
        "alias": idp_alias,
		"enabled": True,
		"updateProfileFirstLoginMode": "on",
		"trustEmail": False,
		"storeToken": False,
		"addReadTokenRoleOnCreate": False,
		"authenticateByDefault": False,
		"linkOnly": False
    },
    headers={
        "Content-Type":	"application/json",
        "Authorization": f"Bearer {admin_token}"
    }
)

# If it exists (status code == 409) we can ignore the "error"
if not idp_create_response.ok and idp_create_response.status_code != 409:
    print(idp_create_response.json())
    exit(1)
print("Idp created or already exists")
