import json
import httpx
import pytest
import pytest_asyncio
import responses
from pytest import mark
from responses import matchers
from unittest import mock
from unittest.mock import mock_open

from controller import start
from exceptions import PodWatcherException


class TestWatcherApiDelivery:
    delivery_content = {"other": {"url": "https://fancyresultsplace.com/api/storage", "auth_type": "Bearer"}}
    delivery_content_basic = {"other": {"url": "https://fancyresultsplace.com/api/storage", "auth_type": "Basic"}}

    @mark.asyncio
    @mark.parametrize('delivery_open', [delivery_content], indirect=True)
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    async def test_get_results_api_delivery(
            self,
            token_mock,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_task_done,
            mock_pod_watch,
            unencoded_bearer,
            domain,
            respx_mock,
            fn_task_results_request
        ):
        """
        Tests that once the task's pod is completed,
        the results are delivered to an API
        """
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]
        # Mock the request response from the Delivery
        respx_mock.post(
            self.delivery_content["other"]["url"],
            headers={"Authorization": f"Bearer {unencoded_bearer}"}
        ).mock(
            return_value=httpx.Response(status_code=201)
        )
        with mock.patch("asyncio.create_task", mock.MagicMock()) as mock_create_task:
            await start(True)
            # Since the watch task pod is a create_task, we need to
            # explicitly call it and await for it
            await mock_create_task.call_args[0][0]

        k8s_client["patch_cluster_custom_object_mock"].assert_called_with(
            'tasks.federatednode.com', 'v1', 'analytics', crd_name,
            [{'op': 'add', 'path': '/metadata/annotations', 'value':
                {
                    f"{domain}/user": "ok",
                    f"{domain}/done": "true",
                    f"{domain}/results": "true",
                    f"{domain}/task_id": "1"
                }
            }]
        )

    @mark.asyncio
    @mark.parametrize('delivery_open', [delivery_content_basic], indirect=True)
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    async def test_get_results_api_delivery_basic(
            self,
            token_mock,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_task_done,
            mock_pod_watch,
            fn_task_results_request,
            encoded_basic,
            respx_mock,
            domain
        ):
        """
        Tests that once the task's pod is completed,
        the results are delivered to an API. Virtually
        behave the same as the bearer auth, but it's to ensure
        we interpret basic auth correctly
        """
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]
        k8s_client["list_namespaced_secret"].return_value.items[0].data["auth"] = encoded_basic

        # Mock the request response from the delivery
        respx_mock.post(
            self.delivery_content["other"]["url"],
            headers={"Authorization": f"Basic {encoded_basic}"}
        ).mock(
            return_value=httpx.Response(status_code=201)
        )
        with mock.patch("asyncio.create_task", mock.MagicMock()) as mock_create_task:
            await start(True)
            # Since the watch task pod is a create_task, we need to
            # explicitly call it and await for it
            await mock_create_task.call_args[0][0]

        k8s_client["patch_cluster_custom_object_mock"].assert_called_with(
            'tasks.federatednode.com', 'v1', 'analytics', crd_name,
            [{'op': 'add', 'path': '/metadata/annotations', 'value':
                {
                    f"{domain}/user": "ok",
                    f"{domain}/done": "true",
                    f"{domain}/results": "true",
                    f"{domain}/task_id": "1"
                }
            }]
        )

    @mark.asyncio
    @mark.parametrize('delivery_open', [delivery_content], indirect=True)
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    async def test_get_results_api_delivery_fails(
            self,
            token_mock,
            k8s_client,
            k8s_watch_mock,
            v1_batch_mock,
            crd_name,
            mock_crd_task_done,
            mock_pod_watch,
            fn_task_results_request,
            respx_mock,
            unencoded_bearer
        ):
        """
        Tests that once the task's pod is completed,
        the results fail to be sent, and will trigger the retry job
        """
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]

        # Mock the request response from the delivery
        respx_mock.post(
            self.delivery_content["other"]["url"],
        ).mock(
            return_value=httpx.Response(status_code=400)
        )
        with mock.patch("asyncio.create_task", mock.MagicMock()) as mock_create_task:
            await start(True)
        with pytest.raises(PodWatcherException):
            # Since the watch task pod is a create_task, we need to
            # explicitly call it and await for it
            await mock_create_task.call_args[0][0]

        # CRD not patched immediately
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()
