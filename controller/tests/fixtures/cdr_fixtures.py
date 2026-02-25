from copy import deepcopy
from typing import Any

import pytest_asyncio

from models.crd import Analytics


def base_crd_object(name:str, type:str="ADDED") -> dict[str, Any]:
    """
    Basic Custom Resource Definition body returned
    by the watcher
    """
    return {
        "object": {
            "metadata": {
                "name": name,
                "annotations": {}
            },
            "spec": {
                "image": "some/docker:tag",
                "project": "project1",
                "outputs": {"path": "/some/other/path"},
                "inputs": {"path": "/some/path"},
                "source": {"repository": "org/repository"}
            }
        },
        "type" : type
    }

def user_crd_object(name:str, type:str="ADDED", udpid:str="") -> dict[str, Any]:
    """
    Basic Custom Resource Definition body returned
    by the watcher
    """

    base: dict[str, Any] = base_crd_object(name, type)
    base["object"]["spec"].update({
        "project": "project1",
        "user": {
          "username": "user2",
          "idpId": udpid,
      }
    })
    return base


@pytest_asyncio.fixture
def crd_object_mock(crd_name) -> Analytics:
    crd_obj: dict[str, Any]= base_crd_object(name=crd_name)
    return Analytics(crd_obj)


@pytest_asyncio.fixture
async def mock_crd(crd_name) -> dict[str, Any]:
    return deepcopy(base_crd_object(name=crd_name))

# User-based
@pytest_asyncio.fixture
def crd_user_object_mock(crd_name, user_idp_id) -> Analytics:
    crd_obj: dict[str, Any]= user_crd_object(name=crd_name, udpid=user_idp_id)
    return Analytics(crd_obj)


@pytest_asyncio.fixture
async def mock_crd_user(crd_name, user_idp_id) -> dict[str, Any]:
    return deepcopy(user_crd_object(name=crd_name, udpid=user_idp_id))


@pytest_asyncio.fixture
async def mock_crd_base_synched(mock_crd):
    mock_crd['type'] = "MODIFIED"
    mock_crd['object']['metadata']['annotations'][f"{Analytics.domain}/user"] = "ok"
    return deepcopy(mock_crd)


@pytest_asyncio.fixture
async def mock_crd_user_synched(mock_crd_user):
    mock_crd_user['type'] = "MODIFIED"
    mock_crd_user['object']['metadata']['annotations'][f"{Analytics.domain}/user"] = "ok"
    return deepcopy(mock_crd_user)


# Mock statuses
@pytest_asyncio.fixture
async def mock_crd_task_done(mock_crd_user_synched):
    mock_crd_user_synched['object']['metadata']['annotations']\
            [f"{Analytics.domain}/done"] = "true"
    mock_crd_user_synched['object']['metadata']['annotations']\
                [f"{Analytics.domain}/task_id"] = "1"
    return deepcopy(mock_crd_user_synched)

@pytest_asyncio.fixture
async def mock_crd_done(mock_crd_task_done):
    mock_crd_task_done['object']['metadata']['annotations']\
            [f"{Analytics.domain}/results"] = "true"
    return deepcopy(mock_crd_task_done)

@pytest_asyncio.fixture
async def mock_crd_azcopy_done(mock_crd_task_done):
    mock_crd_task_done["object"]["spec"]["results"] = {"other": {
        "url": "https://fancyresultsplace.com/api/storage",
        "auth_type": "AzCopy"
    }}
    return deepcopy(mock_crd_task_done)

@pytest_asyncio.fixture
async def mock_crd_api_done(mock_crd_task_done):
    mock_crd_task_done["object"]["spec"]["results"] = {"other": {
        "url": "https://fancyresultsplace.com/api/storage",
        "auth_type": "Bearer"
    }}
    return deepcopy(mock_crd_task_done)

@pytest_asyncio.fixture
async def mock_crd_api_basic_done(mock_crd_task_done):
    mock_crd_task_done["object"]["spec"]["results"] = {"other": {
        "url": "https://fancyresultsplace.com/api/storage",
        "auth_type": "Basic"
    }}
    return deepcopy(mock_crd_task_done)

@pytest_asyncio.fixture
async def mock_crd_azcopy_done(mock_crd_task_done):
    mock_crd_task_done["object"]["spec"]["results"] = {"other": {
        "url": "https://fancyresultsplace.com/api/storage",
        "auth_type": "AzCopy"
    }}
    return deepcopy(mock_crd_task_done)

@pytest_asyncio.fixture
async def mock_crd_api_done(mock_crd_task_done):
    mock_crd_task_done["object"]["spec"]["results"] = {"other": {
        "url": "https://fancyresultsplace.com/api/storage",
        "auth_type": "Bearer"
    }}
    return deepcopy(mock_crd_task_done)

@pytest_asyncio.fixture
async def mock_crd_api_basic_done(mock_crd_task_done):
    mock_crd_task_done["object"]["spec"]["results"] = {"other": {
        "url": "https://fancyresultsplace.com/api/storage",
        "auth_type": "Basic"
    }}
    return deepcopy(mock_crd_task_done)
