import base64
import json
import os
import pytest
import responses
from copy import deepcopy
from kubernetes import client
from unittest.mock import MagicMock, Mock, mock_open

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

@pytest.fixture
def domain():
    return Analytics.domain

@pytest.fixture
def crd_name():
    return "test_task"

@pytest.fixture
def user_idp_id():
    return "123456789"

@pytest.fixture
def user_email():
    return "something@email.com"

@pytest.fixture
def unencoded_bearer():
    return "token"

@pytest.fixture
def encoded_bearer(unencoded_bearer):
    return base64.b64encode(unencoded_bearer.encode()).decode()

@pytest.fixture
def unencoded_basic():
    return "user:pass"

@pytest.fixture
def encoded_basic(unencoded_basic):
    return base64.b64encode(unencoded_basic.encode()).decode()

@pytest.fixture
def mock_crd(crd_name, user_idp_id):
    return deepcopy(base_crd_object(name=crd_name, udpid=user_idp_id))

@pytest.fixture
def mock_crd_user_synched(mock_crd):
    mock_crd['type'] = "MODIFIED"
    mock_crd['object']['metadata']['annotations'][f"{Analytics.domain}/user"] = "ok"
    return deepcopy(mock_crd)

@pytest.fixture
def mock_crd_task_done(mock_crd_user_synched):
    mock_crd_user_synched['object']['metadata']['annotations']\
            [f"{Analytics.domain}/done"] = "true"
    mock_crd_user_synched['object']['metadata']['annotations']\
                [f"{Analytics.domain}/task_id"] = "1"
    return deepcopy(mock_crd_user_synched)

@pytest.fixture
def mock_crd_done(mock_crd_task_done):
    mock_crd_task_done['object']['metadata']['annotations']\
            [f"{Analytics.domain}/results"] = "true"
    return deepcopy(mock_crd_task_done)

@pytest.fixture
def mock_crd_azcopy_done(mock_crd_task_done):
    mock_crd_task_done["object"]["spec"]["results"] = {"other": {
        "url": "https://fancyresultsplace.com/api/storage",
        "auth_type": "AzCopy"
    }}
    return deepcopy(mock_crd_task_done)

@pytest.fixture
def mock_crd_api_done(mock_crd_task_done):
    mock_crd_task_done["object"]["spec"]["results"] = {"other": {
        "url": "https://fancyresultsplace.com/api/storage",
        "auth_type": "Bearer"
    }}
    return deepcopy(mock_crd_task_done)

@pytest.fixture
def mock_crd_api_basic_done(mock_crd_task_done):
    mock_crd_task_done["object"]["spec"]["results"] = {"other": {
        "url": "https://fancyresultsplace.com/api/storage",
        "auth_type": "Basic"
    }}
    return deepcopy(mock_crd_task_done)

@pytest.fixture(autouse=True)
def k8s_config(mocker):
    mocker.patch('kubernetes.config.load_kube_config', return_value=Mock())
    mocker.patch('helpers.kubernetes_helper.load_kube_config', return_value=Mock())

@pytest.fixture
def k8s_watch_mock(mocker):
    return mocker.patch(
        'controller.Watch',
        return_value=Mock(stream=Mock(return_value=[base_crd_object("crd1")]))
    )

@pytest.fixture
def job_spec_mock():
    job = MagicMock(spec=client.V1Job)
    job.mock_add_spec('spec.template.spec.containers')
    return job

@pytest.fixture
def v1_mock(mocker, job_spec_mock, encoded_bearer):
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

@pytest.fixture
def v1_batch_mock(mocker):
    return {
        "create_namespaced_job_mock": mocker.patch(
            'helpers.kubernetes_helper.KubernetesV1Batch.create_namespaced_job'
        )
    }

@pytest.fixture
def v1_crd_mock(mocker):
    return {
        "patch_cluster_custom_object_mock": mocker.patch(
            'helpers.kubernetes_helper.KubernetesCRD.patch_cluster_custom_object', return_value=Mock(
            name="patch_cluster_custom_object_mock")
        )
    }

@pytest.fixture
def k8s_client(mocker, v1_mock, v1_batch_mock, v1_crd_mock, k8s_config, job_spec_mock, k8s_watch_mock, encoded_bearer):
    all_clients = {}
    all_clients.update(v1_mock)
    all_clients.update(v1_batch_mock)
    all_clients.update(v1_crd_mock)
    all_clients["read_namespaced_secret"].return_value.data = {
        "KEYCLOAK_GLOBAL_CLIENT_SECRET": "YWJjMTIz",
        "KEYCLOAK_ADMIN_PASSWORD": "YWJjMTIz"
    }
    return all_clients

@pytest.fixture
def backend_url(mocker):
    return os.getenv("BACKEND_HOST")

@pytest.fixture
def keycloak_url(mocker):
    return os.getenv("KC_HOST")

@pytest.fixture
def keycloak_realm(mocker):
    return "FederatedNode"

@pytest.fixture
def mock_pod_watch(mocker, k8s_client, encoded_bearer):
    return {
        "watch": mocker.patch(
            'helpers.pod_watcher.Watch',
            return_value=Mock(stream=Mock(return_value=[pod_object_response()]))
        )
    }

@pytest.fixture
def mock_job_watch(mocker, k8s_client):
    mocker.patch(
        'helpers.pod_watcher.KubernetesV1Batch',
    )
    mocker.patch(
        'helpers.pod_watcher.Watch',
        return_value=Mock(stream=Mock(return_value=[job_object_response()]))
    )

@pytest.fixture
def fn_task_request(backend_url):
    return responses.Response(
        responses.POST,
        f"{backend_url}/tasks",
        status=200,
        json={"task_id": '1'}
    )

@pytest.fixture
def admin_token_request(keycloak_url, keycloak_realm):
    return responses.Response(
        responses.POST,
        url=f"{keycloak_url}/realms/{keycloak_realm}/protocol/openid-connect/token",
        status=200,
        json={"access_token": "token"}
    )

@pytest.fixture
def get_user_request(user_idp_id, keycloak_url, keycloak_realm):
    return responses.Response(
        responses.GET,
        url=f"{keycloak_url}/admin/realms/{keycloak_realm}/users?idpUserId={user_idp_id}",
        status=200,
        json=[{"id": "asw84r3184"}]
    )

@pytest.fixture
def impersonate_request(keycloak_url, keycloak_realm):
    return responses.Response(
        responses.POST,
        url=f"{keycloak_url}/realms/{keycloak_realm}/protocol/openid-connect/token",
        status=200,
        json={"refresh_token": "refresh_token"}
    )

@pytest.fixture(autouse=True)
def delivery_open(request, mocker):
    mocker.patch("helpers.task_helper.open", mock_open())
    mocker.patch("helpers.pod_watcher.open", mock_open())
    file_contents = {"github": {"repository": "org/repo"}}
    if getattr(request, "param", None):
        file_contents = request.param
    return mocker.patch("models.crd.open", mock_open(read_data=json.dumps(file_contents)))
