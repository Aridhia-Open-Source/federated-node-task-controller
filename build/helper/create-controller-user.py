import logging
import os
import requests
import time


KEYCLOAK_URL = os.getenv('KC_HOST')
KEYCLOAK_PASS = os.getenv('KEYCLOAK_ADMIN_PASSWORD')

logger = logging.getLogger('idp-initializer')
logger.setLevel(logging.INFO)

# Ready check on backend
for i in range(10):
  try:
    hc_resp = requests.get(f"{KEYCLOAK_URL}/realms/FederatedNode")
    if hc_resp.ok:
      break
  except requests.exceptions.ConnectionError:
    logger.info(f"{i+1}/10 - Failed to connect. Will retry in 10 seconds")
  time.sleep(10)

# Login as admin - Wait 10 seconds between retries. The keycloak init job relies on both kc pods to be up
for i in range(10):
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
    logger.info(f"{i+1}/10 - {admin_response.json()}")
    time.sleep(10)
    continue

  break

logger.info("Logged in!")
admin_token = admin_response.json()["access_token"]

def is_response_good(response:requests.Response) -> None:
  if not response.ok and response.status_code != 409:
    logger.error(f"{response.status_code} - {response.text}")
    exit(1)

def get_role(role_name:str, admin_token:str):
    logger.info(f"Getting realms role {role_name} id")
    headers = {
      'Authorization': f'Bearer {admin_token}'
    }

    # Fetch the realm roles
    response = requests.get(
      f"{KEYCLOAK_URL}/admin/realms/FederatedNode/roles",
      params={"search": role_name},
      headers=headers
    )
    is_response_good(response)
    role_id = response.json()[0]["id"]
    logger.info("Got role")

    # Fetch the client roles to allow user list read
    response = requests.get(
      f"{KEYCLOAK_URL}/admin/realms/FederatedNode/clients/{get_rm_client_id()}/roles",
      params={"search": "users"},
      headers=headers
    )
    is_response_good(response)
    role_user_mgmt_ids = [role for role in response.json() if "manage" not in role["name"]]

    # Apply them to the System role
    response = requests.post(
      f"{KEYCLOAK_URL}/admin/realms/FederatedNode/roles-by-id/{role_id}/composites",
      json=role_user_mgmt_ids,
      headers=headers
    )
    is_response_good(response)
    return role_id

def create_user(
      username:str,
      password:str,
      email:str="",
      first_name:str="Task",
      last_name:str="Controller",
      role_name:str="System",
      admin_token:str=None,
      realm:str="FederatedNode"
    ):
    """
    Given a set of info about the user, create in the settings.keycloak_realm and
    assigns it the role as it can't be done all in one call.

    The default role, is Super Administrator, which is basically to ensure the backend
    has full access to it
    """
    headers= {
      'Authorization': f'Bearer {admin_token}'
    }
    response_create_user = requests.post(
      f"{KEYCLOAK_URL}/admin/realms/{realm}/users",
      headers=headers,
      json={
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
        "enabled": "true",
        "emailVerified": "true",
        "username": username,
        "credentials": [
          {
            "type": "password",
            "temporary": False,
            "value": password
          }
        ]
      }
    )
    response_user_id = requests.get(
      f"{KEYCLOAK_URL}/admin/realms/{realm}/users",
      params={"username": username},
      headers=headers
    )
    is_response_good(response_user_id)
    user_id = response_user_id.json()[0]["id"]
    if response_create_user.status_code == 409:
      # Reset its password
      logger.info("User exists, resetting password")

      response_reset_pass = requests.put(
        f"{KEYCLOAK_URL}/admin/realms/{realm}/users/{user_id}/reset-password",
        json={
                "type": "password",
                "temporary": False,
                "value": password
            },
            headers={"Authorization": f"Bearer {admin_token}"}
      )
      is_response_good(response_reset_pass)
    elif not response_create_user.ok:
      logger.error(f"{response_create_user.status_code} - {response_create_user.text}")
      exit(1)

    logger.info(f"Assigning role {role_name} to {username}")

    response_assign_role = requests.post(
      f"{KEYCLOAK_URL}/admin/realms/{realm}/users/{user_id}/role-mappings/realm",
      headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {admin_token}'
      },
      json=[
        {
          "id": get_role(role_name, admin_token),
          "name": role_name
        }
      ]
    )
    is_response_good(response_assign_role)

def get_rm_client_id() -> str:
  client_id_resp = requests.get(
    f"{KEYCLOAK_URL}/admin/realms/FederatedNode/clients",
    params = {"clientId": "realm-management"},
    headers={
      'Authorization': f'Bearer {admin_token}'
    }
  )
  if not client_id_resp.ok:
      logger.error(client_id_resp.content.decode())
      exit(1)
  if not len(client_id_resp.json()):
      logger.error("Could not find project")
      exit(1)

  return client_id_resp.json()[0]["id"]

create_user(
  os.getenv("SYS_USER_EMAIL"),
  os.getenv("SYS_USER_PASS"),
  os.getenv("SYS_USER_EMAIL"),
  admin_token=admin_token
)
