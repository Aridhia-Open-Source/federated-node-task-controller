import os
import pytest
from copy import deepcopy
from unittest.mock import Mock

from const import DOMAIN

def base_crd_object(name:str, type:str="ADDED"):
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
                    "idpId": "",
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
def mock_crd(crd_name):
    return deepcopy(base_crd_object(name=crd_name))

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

@pytest.fixture
def k8s_config(mocker):
    mocker.patch('kubernetes.config.load_kube_config', return_value=Mock())

    mocker.patch(
        'controller.helpers.kubernetes_helper.config',
        side_effect=Mock()
    )

@pytest.fixture
def k8s_watch_mock(mocker):
    return mocker.patch(
        'controller.Watch',
        return_value=Mock(stream=Mock(return_value=[base_crd_object("crd1")]))
    )

@pytest.fixture
def k8s_client(mocker, k8s_watch_mock):
    mocker.patch(
        'helpers.kubernetes_helper.client', Mock()
    )
    mocker.patch(
        'helpers.kubernetes_helper.v1'
    )
    mocker.patch(
        'helpers.kubernetes_helper.v1_batch'
    )
    mocker.patch(
        'helpers.pod_watcher.v1', return_value=Mock()
    )

@pytest.fixture
def k8s_crd(mocker):
    mocker.patch(
        'controller.v1_custom_objects', return_value=Mock()
    )

@pytest.fixture
def get_secret(mocker):
    mocker.patch(
        'helpers.keycloak_helper.get_secret'
    )
    mocker.patch(
        'helpers.kubernetes_helper.v1'
    )

@pytest.fixture
def backend_url(mocker):
    return os.getenv("BACKEND_HOST")

@pytest.fixture
def mock_pod_watch(mocker, k8s_client):
    mocker.patch(
        'helpers.pod_watcher.Watch',
        return_value=Mock(stream=Mock(return_value=[pod_object_response()]))
    )
