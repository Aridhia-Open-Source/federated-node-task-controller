import json
import responses
from pytest import mark
from responses import matchers
from unittest import mock
from unittest.mock import mock_open

from controller import start


class TestWatcherApiDelivery:
    delivery_content = {"other": {"url": "https://fancyresultsplace.com/api/storage", "auth_type": "Bearer"}}
    delivery_content_basic = {"other": {"url": "https://fancyresultsplace.com/api/storage", "auth_type": "Basic"}}

    @mark.parametrize('delivery_open', [delivery_content], indirect=True)
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_get_results_api_delivery(
            self,
            token_mock,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_task_done,
            mock_pod_watch,
            backend_url,
            unencoded_bearer,
            domain,
        ):
        """
        Tests that once the task's pod is completed,
        the results are delivered to an API
        """
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]
        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{backend_url}/tasks/1/results",
                status=200
            )
            rsps.add(
                responses.POST,
                self.delivery_content["other"]["url"],
                status=201,
                match=[matchers.header_matcher({
                    "Authorization": f"Bearer {unencoded_bearer}"
                })]
            )
            start(True)

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

    @mark.parametrize('delivery_open', [delivery_content_basic], indirect=True)
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_get_results_api_delivery_basic(
            self,
            token_mock,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_task_done,
            mock_pod_watch,
            backend_url,
            encoded_basic,
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

        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{backend_url}/tasks/1/results",
                status=200
            )
            rsps.add(
                responses.POST,
                self.delivery_content_basic["other"]["url"],
                status=201,
                match=[matchers.header_matcher({"Authorization": f"Basic {encoded_basic}"})]
            )
            start(True)

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

    @mark.parametrize('delivery_open', [delivery_content], indirect=True)
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_get_results_api_delivery_fails(
            self,
            token_mock,
            k8s_client,
            k8s_watch_mock,
            v1_batch_mock,
            crd_name,
            mock_crd_task_done,
            mock_pod_watch,
            backend_url,
            unencoded_bearer,
        ):
        """
        Tests that once the task's pod is completed,
        the results fail to be sent, and will trigger the retry job
        """
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]

        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{backend_url}/tasks/1/results",
                status=200
            )
            rsps.add(
                responses.POST,
                self.delivery_content["other"]["url"],
                status=400
            )
            start(True)

        # CRD not patched immediately
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()
        # The retry job is triggered
        v1_batch_mock["create_namespaced_job_mock"].assert_called()
