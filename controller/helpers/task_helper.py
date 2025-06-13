"""
Collection of functions to assist in performing FN-task-related operations
"""
import logging
from const import BACKEND_HOST, GIT_HOME, PUBLIC_URL
from exceptions import FederatedNodeException
from helpers.keycloak_helper import get_user, impersonate_user
from helpers.request_helper import client as requests
from models.crd import Analytics

logger = logging.getLogger('task_helpers')
logger.setLevel(logging.INFO)


def get_user_token(user:dict) -> str:
    """
    Simply get a user's token through impersonation.
        It is expected for the argument to have at least one
        key among `email` and `username`
    :returns: user's token
    """
    logger.info("Getting user's token")
    user_id = get_user(**user)["id"]
    return impersonate_user(user_id)

def create_task(crd: Analytics, user_token:str):
    """
    Wrapper to call the Federated Node /tasks endpoint
    """
    task_resp = requests.post(
        f"{BACKEND_HOST}/tasks",
        json=crd.create_task_body(),
        headers={
            "Authorization": f"Bearer {user_token}",
            "project-name": crd.proj_name
        }
    )
    if not task_resp.ok and task_resp.status_code != 409:
        raise FederatedNodeException(task_resp.json())
    logger.info("Task created")
    return task_resp.json()


def get_results(task_id:str, token:str) -> str:
    """
    Gets the tar file with the results, raises an exception
    if the request fails
    """
    logger.info("Getting task %s results", task_id)
    res_resp = requests.get(
        f"{BACKEND_HOST}/tasks/{task_id}/results",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )
    if not res_resp.ok:
        raise FederatedNodeException(res_resp.json())
    filepath = f"{GIT_HOME}/{PUBLIC_URL}-{task_id}-results.tar.gz"
    with open(filepath, "wb") as file:
        file.write(res_resp.content)
    return filepath
