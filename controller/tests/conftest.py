import base64
import json
import os
import httpx
import pytest
import pytest_asyncio
from copy import deepcopy
from kubernetes import client
from unittest.mock import MagicMock, Mock, mock_open

from const import KC_USER
from helpers.keycloak_helper import KEYCLOAK_CLIENT
from models.crd import Analytics

def base_crd_object(name:str, type:str="ADDED", udpid:str=""):
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
                "user": {
                    "username": "user2",
                    "idpId": udpid,
                },
                "image": "some/docker:tag",
                "project": "project1",
                "dataset": {
                    "id": ""
                },
                "source": {"repository": "org/repository"}
            }
        },
        "type" : type
    }

@pytest_asyncio.fixture
def crd_object_mock(crd_name, user_idp_id):
    crd_obj= base_crd_object(name=crd_name, udpid=user_idp_id)
    return Analytics(crd_obj)

def pod_object_response():
    return {
        "object": Mock(
            name="job_obj_resp",
            metadata=Mock(name="job1"),
            status=Mock(
                phase="Succeeded"
            )
        )
    }

def job_object_response():
    return {
        "object": Mock(
            name="job_obj_resp",
            metadata=Mock(name="job1"),
            status=Mock(
                succeeded=1,
                ready=0,
                terminating=0,
                active=0,
                failed=0
            )
        )
    }

@pytest_asyncio.fixture
async def domain():
    return Analytics.domain

@pytest_asyncio.fixture
async def crd_name():
    return "test_task"

@pytest_asyncio.fixture
async def user_idp_id():
    return "123456789"

@pytest_asyncio.fixture
async def user_email():
    return "something@email.com"

@pytest_asyncio.fixture
async def unencoded_bearer():
    return "token"

@pytest_asyncio.fixture
async def encoded_bearer(unencoded_bearer):
    return base64.b64encode(unencoded_bearer.encode()).decode()

@pytest_asyncio.fixture
async def unencoded_basic():
    return "user:pass"

@pytest_asyncio.fixture
async def encoded_basic(unencoded_basic):
    return base64.b64encode(unencoded_basic.encode()).decode()

@pytest_asyncio.fixture
async def mock_crd(crd_name, user_idp_id):
    return deepcopy(base_crd_object(name=crd_name, udpid=user_idp_id))

@pytest_asyncio.fixture
async def mock_crd_user_synched(mock_crd):
    mock_crd['type'] = "MODIFIED"
    mock_crd['object']['metadata']['annotations'][f"{Analytics.domain}/user"] = "ok"
    return deepcopy(mock_crd)

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

@pytest.fixture(autouse=True)
def k8s_config(mocker):
    mocker.patch('kubernetes.config.load_kube_config', return_value=Mock())
    mocker.patch('helpers.kubernetes_helper.load_kube_config', return_value=Mock())

@pytest_asyncio.fixture
async def k8s_watch_mock(mocker):
    return mocker.patch(
        'controller.Watch',
        return_value=Mock(stream=Mock(return_value=[base_crd_object("crd1")]))
    )

@pytest_asyncio.fixture
async def job_spec_mock():
    job = MagicMock(spec=client.V1Job)
    job.mock_add_spec('spec.template.spec.containers')
    return job

@pytest_asyncio.fixture
async def v1_mock(mocker, job_spec_mock, encoded_bearer):
    return {
        "create_persistent_volume_mock": mocker.patch(
            'helpers.kubernetes_helper.KubernetesV1.create_persistent_volume'
        ),
        "create_namespaced_persistent_volume_claim_mock": mocker.patch(
            'helpers.kubernetes_helper.KubernetesV1.create_namespaced_persistent_volume_claim'
        ),
        "read_namespaced_secret": mocker.patch(
            'helpers.kubernetes_helper.KubernetesV1.read_namespaced_secret'
        ),
        "list_namespaced_secret": mocker.patch(
            'helpers.pod_watcher.KubernetesV1.list_namespaced_secret',
            return_value=Mock(items=[Mock(data={"auth": encoded_bearer})])
        ),
        "list_namespaced_pod": mocker.patch(
            'helpers.pod_watcher.KubernetesV1.list_namespaced_pod',
            return_value=Mock(items=[])
        )
    }

@pytest_asyncio.fixture
async def v1_batch_mock(mocker):
    return {
        "create_namespaced_job_mock": mocker.patch(
            'helpers.kubernetes_helper.KubernetesV1Batch.create_namespaced_job'
        )
    }

@pytest_asyncio.fixture
async def v1_crd_mock(mocker):
    return {
        "patch_cluster_custom_object_mock": mocker.patch(
            'helpers.kubernetes_helper.KubernetesCRD.patch_cluster_custom_object', return_value=Mock(
            name="patch_cluster_custom_object_mock")
        )
    }

@pytest_asyncio.fixture
async def k8s_client(mocker, v1_mock, v1_batch_mock, v1_crd_mock, k8s_config, job_spec_mock, k8s_watch_mock, encoded_bearer):
    all_clients = {}
    all_clients.update(v1_mock)
    all_clients.update(v1_batch_mock)
    all_clients.update(v1_crd_mock)
    all_clients["read_namespaced_secret"].return_value.data = {
        "KEYCLOAK_SECRET": "YWJjMTIz",
        "KEYCLOAK_ADMIN_PASSWORD": "YWJjMTIz"
    }
    return all_clients

@pytest_asyncio.fixture
async def backend_url(mocker):
    return os.getenv("BACKEND_HOST")

@pytest_asyncio.fixture
async def keycloak_url(mocker):
    return os.getenv("KC_HOST")

@pytest_asyncio.fixture
async def keycloak_realm(mocker):
    return "FederatedNode"

@pytest_asyncio.fixture
async def mock_pod_watch(mocker, k8s_client, encoded_bearer):
    return {
        "watch": mocker.patch(
            'helpers.pod_watcher.Watch',
            return_value=Mock(stream=Mock(return_value=[pod_object_response()]))
        )
    }

@pytest_asyncio.fixture
async def mock_job_watch(mocker, k8s_client):
    mocker.patch(
        'helpers.pod_watcher.KubernetesV1Batch',
    )
    mocker.patch(
        'helpers.pod_watcher.Watch',
        return_value=Mock(stream=Mock(return_value=[job_object_response()]))
    )

@pytest_asyncio.fixture
async def fn_task_request(backend_url, respx_mock):
    return respx_mock.post(f"{backend_url}/tasks").mock(
        return_value=httpx.Response(status_code=200, json={"task_id": '1'})
    )

@pytest_asyncio.fixture
async def fn_task_results_request(backend_url, respx_mock):
    return respx_mock.get(f"{backend_url}/tasks/1/results").mock(
        return_value=httpx.Response(status_code=200)
    )

@pytest_asyncio.fixture
async def admin_token_request(respx_mock, keycloak_url, keycloak_realm):
    return respx_mock.post(
        f"{keycloak_url}/realms/{keycloak_realm}/protocol/openid-connect/token",
        data={
            'client_id': KEYCLOAK_CLIENT,
            'client_secret': "abc123",
            'grant_type': 'password',
            'username': KC_USER,
            'password': "abc123"
        }
    ).mock(
        return_value=httpx.Response(status_code=200, json={"access_token": "token"})
    )

@pytest_asyncio.fixture
async def get_user_request(respx_mock, user_idp_id, keycloak_url, keycloak_realm):
    return respx_mock.get(f"{keycloak_url}/admin/realms/{keycloak_realm}/users?idpUserId={user_idp_id}").mock(
        return_value=httpx.Response(status_code=200, json=[{"id": "asw84r3184"}])
    )

@pytest_asyncio.fixture
async def impersonate_request(respx_mock, keycloak_url, keycloak_realm):
    return respx_mock.post(f"{keycloak_url}/realms/{keycloak_realm}/protocol/openid-connect/token").mock(
        return_value=httpx.Response(status_code=200, json={"refresh_token": "refresh_token"})
    )

@pytest.fixture(autouse=True)
def delivery_open(request, mocker):
    mocker.patch("helpers.task_helper.open", mock_open())
    mocker.patch("helpers.pod_watcher.open", mock_open())
    file_contents = {"github": {"repository": "org/repo"}}
    if getattr(request, "param", None):
        file_contents = request.param
    return mocker.patch("models.crd.open", mock_open(read_data=json.dumps(file_contents)))

@pytest_asyncio.fixture
async def review_env(monkeypatch):
    monkeypatch.setenv("TASK_REVIEW", "enabled")
