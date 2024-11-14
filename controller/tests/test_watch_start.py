import responses
from unittest import mock
from kubernetes.client.exceptions import ApiException
from unittest.mock import mock_open
from controller import start
from const import DOMAIN


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

    @mock.patch('helpers.pod_watcher.patch_crd_annotations')
    def test_sync_user(
        self,
        annotation_patch_mock,
        k8s_client,
        k8s_watch_mock,
        mock_pod_watch
    ):
        """
        Tests the first step of the CRD lifecycle.
        If has been ADDED, sync the GitHub user in Keycloak
        """
        expected_object = k8s_watch_mock.return_value.stream.return_value
        start(True)
        annotation_patch_mock.assert_called_with(
            expected_object[0]["object"]["metadata"]["name"],
            {f"{DOMAIN}/user": "ok"}
        )

    @mock.patch('helpers.actions.patch_crd_annotations')
    @mock.patch('helpers.actions.watch_user_pod', side_effect=ApiException(reason="ImagePullBackOff"))
    def test_sync_user_fails_create_job(
        self,
        wup_mock,
        annotation_patch_mock,
        k8s_client,
        k8s_watch_mock
    ):
        """
        Tests the first step of the CRD lifecycle.
        If for whichever reason the job fails to create, no annotation is
        added to the CRD, keeping it to the same status
        """
        start(True)
        annotation_patch_mock.assert_not_called()

    @mock.patch('helpers.actions.patch_crd_annotations')
    def test_post_task_successful(
            self,
            annotation_patch_mock,
            get_secret,
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
        annotation_patch_mock.assert_called_with(
            crd_name,
            {
                f"{DOMAIN}/user": "ok",
                f"{DOMAIN}/done": "true",
                f"{DOMAIN}/task_id": "1"
            }
        )

    @mock.patch('helpers.actions.patch_crd_annotations')
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_post_task_fails(
            self,
            token_mock,
            annotation_patch_mock,
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
        annotation_patch_mock.assert_not_called()

    @mock.patch("builtins.open", new_callable=mock_open, read_data="data")
    @mock.patch('helpers.pod_watcher.patch_crd_annotations', return_value="token")
    @mock.patch('helpers.actions.get_user_token', return_value="token")
    def test_get_results(
            self,
            token_mock,
            annotation_patch_mock,
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
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_task_done]
        # Mock the request response from the FN API
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{backend_url}/tasks/1/results",
                status=200
            )
            start(True)
        annotation_patch_mock.assert_called_with(
            crd_name,
            {
                f"{DOMAIN}/user": "ok",
                f"{DOMAIN}/done": "true",
                f"{DOMAIN}/results": "true",
                f"{DOMAIN}/task_id": "1"
            }
        )

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
            mocker.patch('helpers.actions.patch_crd_annotations'),
            mocker.patch('helpers.actions.create_helper_job'),
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
            mocker.patch('helpers.actions.patch_crd_annotations'),
            mocker.patch('helpers.actions.create_helper_job'),
            mocker.patch('helpers.actions.create_task'),
            mocker.patch('helpers.actions.watch_task_pod')
        ]
        mock_crd_done["type"] = "DELETED"
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_done]
        start(True)
        for call in calls_to_assert:
            call.assert_not_called()
