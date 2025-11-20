import pytest
from pytest import mark
from unittest import mock

from controller import start


class TestWatcherAzCopyDelivery:
    delivery_content = {"other": {"url": "https://fancyresultsplace.com/api/storage", "auth_type": "AzCopy"}}

    @pytest.mark.asyncio
    @mark.parametrize('delivery_open', [delivery_content], indirect=True)
    @mock.patch("subprocess.run", return_value=mock.Mock(stdout="Success", stderr=None))
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    async def test_get_results_azcopy_delivery(
            self,
            token_mock,
            subprocees_mock,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_task_done,
            mock_pod_watch,
            fn_task_results_request,
            unencoded_bearer,
            domain
        ):
        """
        Tests that once the task's pod is completed,
        the results are sent through AzCopy to a storage account
        """
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]
        await start(True)

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
        subprocees_mock.assert_called_with(
            [
                "azcopy", "copy",
                "/data/controller/localhost-1-results.zip",
                unencoded_bearer
            ],
            **{"capture_output":True, "check": False}
        )

    @pytest.mark.asyncio
    @mark.parametrize('delivery_open', [delivery_content], indirect=True)
    @mock.patch("subprocess.run", return_value=mock.Mock(stdout="In progress", stderr="Failed!"))
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    async def test_get_results_azcopy_delivery_fails(
            self,
            token_mock,
            subprocees_mock,
            k8s_client,
            k8s_watch_mock,
            v1_batch_mock,
            crd_name,
            mock_crd_task_done,
            mock_pod_watch,
            fn_task_results_request,
            unencoded_bearer
        ):
        """
        Tests that once the task's pod is completed,
        the results fail to be sent through AzCopy to a storage account
        and the retry job is triggered
        """
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]
        await start(True)

        subprocees_mock.assert_called_with(
            [
                "azcopy", "copy",
                "/data/controller/localhost-1-results.zip",
                unencoded_bearer
            ],
            **{"capture_output":True, "check": False}
        )
        # CRD not patched immediately
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()
        v1_batch_mock["create_namespaced_job_mock"].assert_called()
