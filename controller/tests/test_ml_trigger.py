import httpx
import pytest
from kubernetes.client.exceptions import ApiException
from unittest import mock
from unittest.mock import AsyncMock

from controller import start
from exceptions import CRDException


class TestMLTriggers:
    @pytest.mark.asyncio
    async def test_basic_trigger(
        self,
        k8s_client,
        k8s_watch_mock,
        mock_crd_user_synched,
        dagster_graphql_mock,
        domain
    ):
        """
        Basic test with a successful graphql submission
        and annotation update
        """
        mock_crd_user_synched['object']['spec']["ml"] = True
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_user_synched]

        await start(True)
        k8s_client["patch_cluster_custom_object_mock"].assert_called_with(
            'tasks.federatednode.com', 'v1', 'analytics', 'test_task',
            [{'op': 'add', 'path': '/metadata/annotations', 'value':
                {
                    f"{domain}/user": "ok",
                    f"{domain}/task_id": "uuid",
                    f"{domain}/done": "true",
                    f"{domain}/results": "ok"
                }
            }]
        )

    @pytest.mark.asyncio
    @mock.patch('controller.create_retry_job')
    async def test_failure_handled_trigger(
        self,
        create_retry_job_mock,
        k8s_client,
        k8s_watch_mock,
        mock_crd_user_synched,
        dagster_graphql_fail_mock,
        domain
    ):
        """
        Basic test with an unsuccessful graphql submission
        and the retry job is created
        """
        mock_crd_user_synched['object']['spec']["ml"] = True
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_user_synched]

        await start(True)
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()
        create_retry_job_mock.assert_called()
