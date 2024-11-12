import os
import pytest
import responses
from copy import deepcopy
from unittest.mock import Mock

from const import DOMAIN

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
                    "username": "",
                    "idpId": udpid,
                },
                "image": "",
                "project": "",
                "dataset": "",
                "repository": "",
            }
        },
        "type" : type
    }

def pod_object_response():
    return {
        "object": Mock(
            metadata=Mock(name="pod1"),
            status=Mock(phase="Succeeded")
        )
    }

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
def mock_crd(crd_name, user_idp_id):
    return deepcopy(base_crd_object(name=crd_name, udpid=user_idp_id))

@pytest.fixture
def mock_crd_user_synched(mock_crd):
    mock_crd['type'] = "MODIFIED"
    mock_crd['object']['metadata']['annotations'][f"{DOMAIN}/user"] = "ok"
    return deepcopy(mock_crd)

@pytest.fixture
def mock_crd_task_done(mock_crd_user_synched):
    mock_crd_user_synched['object']['metadata']['annotations']\
            [f"{DOMAIN}/done"] = "true"
    mock_crd_user_synched['object']['metadata']['annotations']\
                [f"{DOMAIN}/task_id"] = "1"
    return deepcopy(mock_crd_user_synched)

@pytest.fixture
def mock_crd_done(mock_crd_task_done):
    mock_crd_task_done['object']['metadata']['annotations']\
            [f"{DOMAIN}/results"] = "true"
    return deepcopy(mock_crd_task_done)

@pytest.fixture(autouse=True)
def k8s_config(mocker):
    mocker.patch('kubernetes.config.load_kube_config', return_value=Mock())
    mocker.patch('helpers.kubernetes_helper.config.load_kube_config', return_value=Mock())

@pytest.fixture
def k8s_watch_mock(mocker):
    return mocker.patch(
        'controller.Watch',
        return_value=Mock(stream=Mock(return_value=[base_crd_object("crd1")]))
    )

@pytest.fixture
def k8s_client(mocker, k8s_watch_mock):
    return {
        "kh_client": mocker.patch(
            'helpers.kubernetes_helper.client', Mock()
        ),
        "kh_v1_client": mocker.patch(
            'helpers.kubernetes_helper.v1'
        ),
        "kh_v1_batch_client": mocker.patch(
            'helpers.kubernetes_helper.v1_batch'
        ),
        "pv_v1_client": mocker.patch(
            'helpers.pod_watcher.v1', return_value=Mock()
        )
    }

@pytest.fixture
def k8s_crd(mocker):
    mocker.patch(
        'controller.v1_custom_objects', return_value=Mock()
    )

@pytest.fixture
def get_secret(mocker):
    mocker.patch(
        'helpers.keycloak_helper.get_secret', return_value="secretestsecret"
    )
    mocker.patch(
        'helpers.kubernetes_helper.v1'
    )

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
def mock_pod_watch(mocker, k8s_client):
    mocker.patch(
        'helpers.pod_watcher.Watch',
        return_value=Mock(stream=Mock(return_value=[pod_object_response()]))
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
