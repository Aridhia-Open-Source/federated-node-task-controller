import pytest
import responses
from kubernetes.client.exceptions import ApiException
from responses import matchers
from unittest import mock
from unittest.mock import mock_open

from controller import start
from const import DOMAIN
from excpetions import KubernetesException


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
        mock_job_watch
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
                    f"{DOMAIN}/user": "ok"
                }
            }]
        )

    @mock.patch('helpers.actions.watch_user_pod', side_effect=ApiException(reason="ImagePullBackOff"))
    def test_sync_user_fails_create_job(
        self,
        wup_mock,
        k8s_client,
        k8s_watch_mock
    ):
        """
        Tests the first step of the CRD lifecycle.
        If for whichever reason the job fails to create, no annotation is
        added to the CRD, keeping it to the same status
        """
        start(True)
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()

    def test_sync_user_job_fails_run(
        self,
        k8s_client,
        k8s_watch_mock,
        mock_job_watch
    ):
        """
        Tests the first step of the CRD lifecycle.
        If, for whichever reason, the job fails during execute,
        no annotation is added to the CRD,
        keeping it to the same status
        """
        mock_job_watch["watch"].return_value.stream.return_value = [{"object": mock.Mock(status="Failed")}]

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
            k8s_watch_mock
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
                    f"{DOMAIN}/user": "ok",
                    f"{DOMAIN}/done": "true",
                    f"{DOMAIN}/task_id": "1"
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

    def test_get_results_not_reviewed(
            self,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_task_done,
        ):
        """
        Tests that once the task's pod is completed,
        a new github job pusher is created
        """
        k8s_watch_mock.assert_not_called()
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()

    @mock.patch("builtins.open", new_callable=mock_open, read_data="data")
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_get_results_approved(
            self,
            token_mock,
            open_mock,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_task_done,
            mock_pod_watch,
            backend_url
        ):
        """
        Tests that once the task's pod is completed,
        a new github job pusher is created
        """
        mock_crd_task_done['object']['metadata']['annotations']\
                [f"{DOMAIN}/approved"] = "true"
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]
        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{backend_url}/tasks/1/results",
                status=200
            )
            start(True)

        k8s_client["patch_cluster_custom_object_mock"].assert_called_with(
            'tasks.federatednode.com', 'v1', 'analytics', crd_name,
            [{'op': 'add', 'path': '/metadata/annotations', 'value':
                {
                    f"{DOMAIN}/user": "ok",
                    f"{DOMAIN}/done": "true",
                    f"{DOMAIN}/results": "true",
                    f"{DOMAIN}/approved": "true",
                    f"{DOMAIN}/task_id": "1"
                }
            }]
        )

    @mock.patch("builtins.open", new_callable=mock_open, read_data="data")
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_get_results_task_fails(
            self,
            token_mock,
            open_mock,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_task_done,
            mock_pod_watch,
            backend_url
        ):
        """
        Tests that once the task's pod is completed,
        a new github job pusher is created
        """
        mock_pod_watch["watch"].return_value.stream.return_value = [{"object": mock.Mock(status=mock.Mock(phase="Failed"))}]
        mock_crd_task_done['object']['metadata']['annotations']\
                [f"{DOMAIN}/approved"] = "true"
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]
        start(True)

        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()

    def test_get_results_blocked(
            self,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_task_done,
            backend_url
        ):
        """
        Tests that once the task's pod is completed,
        a new github job pusher is created
        """
        mock_crd_task_done['object']['metadata']['annotations']\
                [f"{DOMAIN}/approved"] = "false"
        k8s_watch_mock.assert_not_called()
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()

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
        start(True)

        for call in calls_to_assert:
            call.assert_not_called()


class TestWatcherAzCopyDelivery:

    @mock.patch("subprocess.run", return_value=mock.Mock(stdout="Success", stderr=None))
    @mock.patch("builtins.open", new_callable=mock_open, read_data="data")
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_get_results_azcopy_delivery(
            self,
            token_mock,
            open_mock,
            subprocees_mock,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_azcopy_done,
            mock_pod_watch,
            backend_url,
            unencoded_bearer
        ):
        """
        Tests that once the task's pod is completed,
        the results are sent through AzCopy to a storage account
        """
        mock_crd_azcopy_done['object']['metadata']['annotations']\
                [f"{DOMAIN}/approved"] = "true"
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_azcopy_done]
        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{backend_url}/tasks/1/results",
                status=200
            )
            start(True)

        k8s_client["patch_cluster_custom_object_mock"].assert_called_with(
            'tasks.federatednode.com', 'v1', 'analytics', crd_name,
            [{'op': 'add', 'path': '/metadata/annotations', 'value':
                {
                    f"{DOMAIN}/user": "ok",
                    f"{DOMAIN}/done": "true",
                    f"{DOMAIN}/results": "true",
                    f"{DOMAIN}/approved": "true",
                    f"{DOMAIN}/task_id": "1"
                }
            }]
        )
        subprocees_mock.assert_called_with(
            [
                "azcopy", "copy",
                "/data/controller/localhost-1-results.tar.gz",
                unencoded_bearer
            ],
            **{"capture_output":True, "check": False}
        )

    @mock.patch("subprocess.run", return_value=mock.Mock(stdout="In progress", stderr="Failed!"))
    @mock.patch("builtins.open", new_callable=mock_open, read_data="data")
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_get_results_azcopy_delivery_fails(
            self,
            token_mock,
            open_mock,
            subprocees_mock,
            k8s_client,
            k8s_watch_mock,
            v1_batch_mock,
            crd_name,
            mock_crd_azcopy_done,
            mock_pod_watch,
            backend_url,
            unencoded_bearer
        ):
        """
        Tests that once the task's pod is completed,
        the results fail to be sent through AzCopy to a storage account
        and the retry job is triggered
        """
        mock_crd_azcopy_done['object']['metadata']['annotations']\
                [f"{DOMAIN}/approved"] = "true"
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_azcopy_done]
        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{backend_url}/tasks/1/results",
                status=200
            )
            start(True)

        subprocees_mock.assert_called_with(
            [
                "azcopy", "copy",
                "/data/controller/localhost-1-results.tar.gz",
                unencoded_bearer
            ],
            **{"capture_output":True, "check": False}
        )
        # CRD not patched immediately
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()
        # The retry job is triggered
        v1_batch_mock["create_namespaced_job_mock"].assert_called()


class TestWatcherApiDelivery:
    @mock.patch("builtins.open", new_callable=mock_open, read_data="data")
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_get_results_api_delivery(
            self,
            token_mock,
            open_mock,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_api_done,
            mock_pod_watch,
            backend_url,
            unencoded_bearer
        ):
        """
        Tests that once the task's pod is completed,
        the results are delivered to an API
        """
        mock_crd_api_done['object']['metadata']['annotations']\
                [f"{DOMAIN}/approved"] = "true"
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_api_done]
        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{backend_url}/tasks/1/results",
                status=200
            )
            rsps.add(
                responses.POST,
                mock_crd_api_done["object"]["spec"]["results"]["other"]["url"],
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
                    f"{DOMAIN}/user": "ok",
                    f"{DOMAIN}/done": "true",
                    f"{DOMAIN}/results": "true",
                    f"{DOMAIN}/approved": "true",
                    f"{DOMAIN}/task_id": "1"
                }
            }]
        )

    @mock.patch("builtins.open", new_callable=mock_open, read_data="data")
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_get_results_api_delivery_basic(
            self,
            token_mock,
            open_mock,
            k8s_client,
            k8s_watch_mock,
            crd_name,
            mock_crd_api_basic_done,
            mock_pod_watch,
            backend_url,
            encoded_basic
        ):
        """
        Tests that once the task's pod is completed,
        the results are delivered to an API. Virtually
        behave the same as the bearer auth, but it's to ensure
        we interpret basic auth correctly
        """
        mock_crd_api_basic_done['object']['metadata']['annotations']\
                [f"{DOMAIN}/approved"] = "true"
        k8s_client["list_namespaced_secret"].return_value.items[0].data["auth"] = encoded_basic
        crd_auth = mock_crd_api_basic_done["object"]["spec"]["results"]["other"]

        k8s_watch_mock.return_value.stream.return_value = [mock_crd_api_basic_done]
        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{backend_url}/tasks/1/results",
                status=200
            )
            rsps.add(
                responses.POST,
                crd_auth["url"],
                status=201,
                match=[matchers.header_matcher({"Authorization": f"Basic {encoded_basic}"})]
            )
            start(True)

        k8s_client["patch_cluster_custom_object_mock"].assert_called_with(
            'tasks.federatednode.com', 'v1', 'analytics', crd_name,
            [{'op': 'add', 'path': '/metadata/annotations', 'value':
                {
                    f"{DOMAIN}/user": "ok",
                    f"{DOMAIN}/done": "true",
                    f"{DOMAIN}/results": "true",
                    f"{DOMAIN}/approved": "true",
                    f"{DOMAIN}/task_id": "1"
                }
            }]
        )

    @mock.patch("builtins.open", new_callable=mock_open, read_data="data")
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_get_results_api_delivery_fails(
            self,
            token_mock,
            open_mock,
            k8s_client,
            k8s_watch_mock,
            v1_batch_mock,
            crd_name,
            mock_crd_api_done,
            mock_pod_watch,
            backend_url
        ):
        """
        Tests that once the task's pod is completed,
        the results fail to be sent, and will trigger the retry job
        """
        mock_crd_api_done['object']['metadata']['annotations']\
                [f"{DOMAIN}/approved"] = "true"
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_api_done]
        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{backend_url}/tasks/1/results",
                status=200
            )
            rsps.add(
                responses.POST,
                mock_crd_api_done["object"]["spec"]["results"]["other"]["url"],
                status=400
            )
            start(True)

        # CRD not patched immediately
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()
        # The retry job is triggered
        v1_batch_mock["create_namespaced_job_mock"].assert_called()
