"""
Collection of functions to assist in performing FN-task-related operations
"""
import logging
from controller.const import BACKEND_HOST, GIT_HOME
from controller.excpetions import FederatedNodeException
from .keycloak_helper import get_user, impersonate_user
from .request_helper import client as requests


logger = logging.getLogger('task_helpers')
logger.setLevel(logging.INFO)


def create_task_body(image:str, user:str, project:str, dataset: int):
    """
    The task body is fairly strict, so we are going to inject few
    custom data in it, like a docker image, a user, a project name and the dataset
    to run the task on
    """
    return {
        "name": user,
        "executors": [
            {
                "image": image,
                "env": {}
            }
        ],
        "tags": {
            "dataset_id": dataset,
            "test_tag": "some content"
        },
        "inputs":{},
        "outputs":{},
        "resources": {
            "limits": {
                "cpu": "100m",
                "memory": "100Mi"
            },
            "requests": {
                "cpu": "0.1",
                "memory": "50Mi"
            }
        },
        "volumes": {},
        "description": project
    }

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


def create_task(image:str, name:str, proj_name:str, dataset_id:str, user_token:str):
    """
    Wrapper to call the Federated Node /tasks endpoint
    """
    task_resp = requests.post(
        f"{BACKEND_HOST}/tasks",
        json=create_task_body(
            image,
            name,
            proj_name,
            dataset_id
        ),
        verify=False,
        headers={
            "Authorization": f"Bearer {user_token}",
            "project-name": proj_name
        }
    )
    if not task_resp.ok and task_resp.status_code != 409:
        raise FederatedNodeException(task_resp.json())
    logger.info("Task created")
    return task_resp.json()


def check_status(task_id:str, token:str) -> dict:
    """
    Get the task status
    """
    logger.info("Checking task %s status", task_id)
    status_check = requests.get(
        f"{BACKEND_HOST}/tasks/{task_id}",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )
    if not status_check.ok:
        raise FederatedNodeException(status_check.json())
    return status_check.json()["status"]

def get_results(task_id:str, token:str):
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
    with open(f"{GIT_HOME}/results.tar.gz", "wb") as file:
        file.write(res_resp.content)
