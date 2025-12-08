"""
Collection of functions to assist in performing FN-task-related operations
"""
import logging

import httpx
from const import BACKEND_HOST, GIT_HOME, PUBLIC_URL
from exceptions import FederatedNodeException
from helpers.keycloak_helper import get_user, impersonate_user
from models.crd import Analytics

logger = logging.getLogger('task_helpers')
logger.setLevel(logging.INFO)


async def get_user_token(user:dict) -> str:
    """
    Simply get a user's token through impersonation.
        It is expected for the argument to have at least one
        key among `email` and `username`
    :returns: user's token
    """
    logger.info("Getting user's token")
    user_info = await get_user(**user)
    return await impersonate_user(user_info["id"])

def create_fn_task(crd: Analytics, user_token:str) -> dict[str,str]:
    """
    Wrapper to call the Federated Node /tasks endpoint
    """
    task_resp = httpx.post(
        f"{BACKEND_HOST}/tasks",
        json=crd.create_task_body(),
        headers={
            "Authorization": f"Bearer {user_token}",
            "project-name": crd.proj_name
        }
    )
    if task_resp.status_code > 299 and task_resp.status_code != 409:
        raise FederatedNodeException(task_resp.json())
    logger.info("Task created")
    return task_resp.json()

async def get_results(task_id:str, token:str) -> str:
    """
    Gets the tar file with the results, raises an exception
    if the request fails
    """
    logger.info("Getting task %s results", task_id)
    res_resp = httpx.get(
        f"{BACKEND_HOST}/tasks/{task_id}/results",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )
    if res_resp.status_code > 299:
        if res_resp.json().get('status') == "Pending Review":
            return
        raise FederatedNodeException(res_resp.json())
    filepath = f"{GIT_HOME}/{PUBLIC_URL}-{task_id}-results.zip"
    with open(filepath, "wb") as file:
        file.write(res_resp.content)
    return filepath

async def create_system_user(task_id:str, token:str) -> str:
    """
    Gets the tar file with the results, raises an exception
    if the request fails
    """
    logger.info("Getting task %s results", task_id)
    res_resp = httpx.get(
        f"{BACKEND_HOST}/tasks/{task_id}/results",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )
    if res_resp.status_code > 299:
        if res_resp.json().get('status') == "Pending Review":
            return
        raise FederatedNodeException(res_resp.json())
    filepath = f"{GIT_HOME}/{PUBLIC_URL}-{task_id}-results.zip"
    with open(filepath, "wb") as file:
        file.write(res_resp.content)
    return filepath
