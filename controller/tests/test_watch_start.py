import pytest
import responses
from kubernetes.client.exceptions import ApiException
from unittest import mock
from unittest.mock import mock_open

from controller import start
from excpetions import CRDException


class TestWatcher:
    def expected_labels(self, specs:dict={}):
        return {
            "image": specs["image"],
            "project": specs["project"],
            "dataset": specs["dataset"],
            "repository": specs["repository"],
            "username": specs["user"]["username"],
            "idpId": specs["user"]["idpId"],
            "tasks.federatednode.com": "fn-controller"
        }

    def test_sync_user(
        self,
        k8s_client,
        k8s_watch_mock,
        mock_job_watch,
        delivery_open,
        domain
    ):
        """
        Tests the first step of the CRD lifecycle.
        If has been ADDED, sync the GitHub user in Keycloak
        """
        start(True)
        k8s_client["patch_cluster_custom_object_mock"].assert_called_with(
            'tasks.federatednode.com', 'v1', 'analytics', 'crd1',
            [{'op': 'add', 'path': '/metadata/annotations', 'value':
                {
                    f"{domain}/user": "ok"
                }
            }]
        )

    @mock.patch('helpers.actions.watch_user_pod', side_effect=ApiException(reason="ImagePullBackOff"))
    def test_sync_user_fails_create_job(
        self,
        wup_mock,
        k8s_client,
        k8s_watch_mock,
        delivery_open
    ):
        """
        Tests the first step of the CRD lifecycle.
        If for whichever reason the job fails to create, no annotation is
        added to the CRD, keeping it to the same status
        """
        start(True)
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()

    def test_post_task_successful(
            self,
            mock_crd_user_synched,
            admin_token_request,
            impersonate_request,
            get_user_request,
            fn_task_request,
            crd_name,
            k8s_client,
            k8s_watch_mock,
            domain
        ):
        """
        Tests that the task request is sent to the FN
        if the user annotation is set.
        """
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_user_synched]

        # Mock the request response from the FN API
        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(fn_task_request)
            rsps.add(get_user_request)
            rsps.add(admin_token_request)
            rsps.add(admin_token_request)
            rsps.add(impersonate_request)
            start(True)

        k8s_client["patch_cluster_custom_object_mock"].assert_called_with(
            'tasks.federatednode.com', 'v1', 'analytics', crd_name,
            [{'op': 'add', 'path': '/metadata/annotations', 'value':
                {
                    f"{domain}/user": "ok",
                    f"{domain}/done": "true",
                    f"{domain}/task_id": "1"
                }
            }]
        )

    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_post_task_fails(
            self,
            token_mock,
            mock_crd_user_synched,
            crd_name,
            k8s_client,
            k8s_watch_mock,
            backend_url
        ):
        """
        Tests that no annotations are updated
        in case the post task request fails
        """
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_user_synched]
        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                f"{backend_url}/tasks",
                status=400,
                json={"error": 'Something went wrong'}
            )
            start(True)

        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()

    @mock.patch("builtins.open", new_callable=mock_open, read_data="data")
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_get_results(
            self,
            token_mock,
            open_mock,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_task_done,
            mock_pod_watch,
            backend_url,
            delivery_open,
            domain
        ):
        """
        Tests that once the task's pod is completed,
        a new github job pusher is created. In this case only
        the CRD won't be patched by the controller itself,
        but by the result job
        """
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]
        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{backend_url}/tasks/1/results",
                status=200
            )
            start(True)

        k8s_client["create_namespaced_job_mock"].assert_called()

    def test_ignore_done_crd(
            self,
            k8s_client,
            k8s_watch_mock,
            mock_crd_done,
            mocker
        ):
        """
        Tests that once the CRD lifecycle is completed,
        nothing is done, and it's plain ignored.
        This happens after the controller restarts
        due to chart upgrades
        """
        calls_to_assert =[
            k8s_client["patch_cluster_custom_object_mock"],
            mocker.patch('helpers.actions.KubernetesV1Batch.create_helper_job'),
            mocker.patch('helpers.actions.create_task'),
            mocker.patch('helpers.actions.watch_task_pod')
        ]
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_done]
        start(True)
        for call in calls_to_assert:
            call.assert_not_called()

    def test_deleted_crd_is_ignored(
            self,
            k8s_client,
            k8s_watch_mock,
            mock_crd_done,
            mocker
        ):
        """
        Tests that a deleted CRD it's plain ignored.
        """
        calls_to_assert =[
            k8s_client["patch_cluster_custom_object_mock"],
            mocker.patch('helpers.actions.KubernetesV1Batch.create_helper_job'),
            mocker.patch('helpers.actions.create_task'),
            mocker.patch('helpers.actions.watch_task_pod')
        ]
        mock_crd_done["type"] = "DELETED"
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_done]
        start(True)
        for call in calls_to_assert:
            call.assert_not_called()

    def test_incomplete_crd_fields(
            self,
            k8s_client,
            k8s_watch_mock,
            mock_crd_done,
            mocker
        ):
        """
        Tests that a CRD with missing expected fields it's not parsed.
        """
        k8s_watch_mock.return_value.stream.return_value[0]["object"]["spec"].pop("user")
        calls_to_assert =[
            k8s_client["patch_cluster_custom_object_mock"],
            mocker.patch('helpers.actions.KubernetesV1Batch.create_helper_job'),
            mocker.patch('helpers.actions.create_task'),
            mocker.patch('helpers.actions.watch_task_pod')
        ]
        with pytest.raises(CRDException):
            start(True)

        for call in calls_to_assert:
            call.assert_not_called()

    @mock.patch("builtins.open", new_callable=mock_open, read_data="data")
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_missing_result_crd_fields(
            self,
            token_mock,
            open_mock,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_task_done,
            mock_pod_watch,
            backend_url,
            delivery_open,
            domain
        ):
        """
        Tests that a CRD with missing results fields will by default create a github delivery
        """
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]
        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{backend_url}/tasks/1/results",
                status=200
            )
            start(True)
        requested_env = k8s_client["create_namespaced_job_mock"].call_args[1]["body"].spec.template.spec.containers[0].env
        assert 'org/repo' in [env.value for env in requested_env if env.name == "GH_REPO"]

    @mock.patch("builtins.open", new_callable=mock_open, read_data="data")
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    @mock.patch('controller.create_retry_job')
    @mock.patch('helpers.pod_watcher.MAX_TIMEOUT', 1)
    def test_watch_timeouts(
            self,
            create_retry_job_mock,
            token_mock,
            open_mock,
            k8s_client,
            k8s_watch_mock,
            mock_crd_task_done,
            mock_pod_watch
        ):
        """
        Tests that a CRD with an incorrect task_id (due to the pod manually deleted)
        raises an exception instead of hanging
        """
        import time

        def mock_stream(*args, **kwargs):
            yield from []
            # Optionally, you could simulate a short delay to ensure the timeout is reached
            time.sleep(kwargs.get('timeout_seconds', 1) + 0.5)

        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]
        mock_pod_watch["watch"].return_value.stream.side_effect = mock_stream
        start(True)
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()
        create_retry_job_mock.assert_called()
