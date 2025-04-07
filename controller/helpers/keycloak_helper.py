"""
Both kubernetes and keycloak standard operations
- for k8s we just set the configuration
- keycloak will have different functions in a way
    to not tamper the __main__ with API calls and the
    status_code checks
"""

import os
import logging

from excpetions import KeycloakException
from helpers.kubernetes_helper import KubernetesV1
from helpers.request_helper import client as requests
from const import KC_USER, KC_HOST

logger = logging.getLogger('keycloak_helper')
logger.setLevel(logging.INFO)


KEYCLOAK_CLIENT = "global"
REALM = "FederatedNode"
KC_HOST = os.getenv("KC_HOST")


def get_keycloak_secret() -> str:
    """
    Simple generalization to get keycloak secret, as it has
    fixed keys in it
    """
    return KubernetesV1().get_secret('kc-secrets', 'KEYCLOAK_GLOBAL_CLIENT_SECRET')

def get_keycloak_admin_pass() -> str:
    """
    Simple generalization to get the specific admin key
    for the keycloak secret
    """
    return KubernetesV1().get_secret('kc-secrets', 'KEYCLOAK_ADMIN_PASSWORD')

def get_admin_token() -> str:
    """
    Simply send a request to Keycloak to get the admin token
    based on the password fetched from the k8s secret itself
    """
    admin_resp = requests.post(
        f"{KC_HOST}/realms/{REALM}/protocol/openid-connect/token",
        data={
            'client_id': KEYCLOAK_CLIENT,
            'client_secret': get_keycloak_secret(),
            'grant_type': 'password',
            'username': KC_USER,
            'password': get_keycloak_admin_pass()
        },
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    )
    if not admin_resp.ok:
        raise KeycloakException("Failed to login")
    return admin_resp.json()["access_token"]


def get_user(email:str=None, username:str=None, idpId:str=None) -> dict:
    """
    Method to return a dictionary representing a Keycloak user
    """
    if idpId:
        user_response = requests.get(
            f"{KC_HOST}/admin/realms/{REALM}/users?idpUserId={idpId}",
            headers={"Authorization": f"Bearer {get_admin_token()}"}
        )
    elif email:
        user_response = requests.get(
            f"{KC_HOST}/admin/realms/{REALM}/users?email={email}&exact=true",
            headers={"Authorization": f"Bearer {get_admin_token()}"}
        )
    elif username:
        user_response = requests.get(
            f"{KC_HOST}/admin/realms/{REALM}/users?username={username}&exact=true",
            headers={"Authorization": f"Bearer {get_admin_token()}"}
        )
    else:
        raise KeycloakException("Either email or username are needed")
    if not user_response.ok:
        raise KeycloakException(user_response.content.decode())
    if len(user_response.json()):
        return user_response.json()[0]

    raise KeycloakException(f"User {email or idpId or username} not found")


def impersonate_user(user_id:str) -> str:
    """
    Given a user id, it will return a refresh_token for it
    through the admin-level user
    """
    exchange_resp = requests.post(
        f"{KC_HOST}/realms/{REALM}/protocol/openid-connect/token",
        data={
            'client_secret': get_keycloak_secret(), # Target client
            'client_id': KEYCLOAK_CLIENT, #Target client
            'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
            'requested_token_type': 'urn:ietf:params:oauth:token-type:refresh_token',
            'subject_token': get_admin_token(),
            'requested_subject': user_id,
            'audience': KEYCLOAK_CLIENT
        },
        headers={
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    )
    if not exchange_resp.ok:
        raise KeycloakException(exchange_resp.content.decode())
    return exchange_resp.json()["refresh_token"]
