import responses
from unittest import mock
from const import DOMAIN
from controller import start


class TestKeycloakRequests:
    @mock.patch('controller.patch_crd_annotations')
    def test_user_auth_fails(
            self,
            annotation_patch_mock,
            get_secret,
            mock_crd_user_synched,
            k8s_client,
            k8s_watch_mock,
            get_user_request,
            admin_token_request,
            keycloak_url,
            keycloak_realm
        ):
        """
        Tests that the task request is not sent if impersonation fails
        """
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_user_synched]

        with responses.RequestsMock() as rsps:
            rsps.add(get_user_request)
            rsps.add(admin_token_request)
            rsps.add(admin_token_request)
            # Impersonation
            rsps.add(
                responses.POST,
                url=f"{keycloak_url}/realms/{keycloak_realm}/protocol/openid-connect/token",
                status=403,
                json={"error": "Unauthorized"}
            )
            start(True)

        annotation_patch_mock.assert_not_called()

    @mock.patch('controller.patch_crd_annotations')
    def test_email_provided_in_crd(
            self,
            annotation_patch_mock,
            get_secret,
            mock_crd_user_synched,
            crd_name,
            k8s_client,
            user_email,
            keycloak_url,
            keycloak_realm,
            k8s_watch_mock,
            admin_token_request,
            impersonate_request,
            fn_task_request
        ):
        """
        Tests that the task request is sent to the FN
        if the CRD user field only has email
        """
        mock_crd_user_synched['object']['spec']['user'] = {"email": user_email}
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_user_synched]

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                url=f"{keycloak_url}/admin/realms/{keycloak_realm}/users?email={user_email}&exact=true",
                status=200,
                json=[{"id": "asw84r3184"}]
            )
            rsps.add(admin_token_request)
            rsps.add(admin_token_request)
            rsps.add(fn_task_request)
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

    @mock.patch('controller.patch_crd_annotations')
    def test_username_provided_in_crd(
            self,
            annotation_patch_mock,
            get_secret,
            mock_crd_user_synched,
            crd_name,
            k8s_client,
            user_email,
            keycloak_url,
            keycloak_realm,
            k8s_watch_mock,
            admin_token_request,
            impersonate_request,
            fn_task_request
        ):
        """
        Tests that the task request is sent to the FN
        if the CRD user field only has email
        """
        mock_crd_user_synched['object']['spec']['user'] = {"username": user_email}
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_user_synched]

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                url=f"{keycloak_url}/admin/realms/{keycloak_realm}/users?username={user_email}&exact=true",
                status=200,
                json=[{"id": "asw84r3184"}]
            )
            rsps.add(admin_token_request)
            rsps.add(admin_token_request)
            rsps.add(fn_task_request)
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

    @mock.patch('controller.create_task')
    @mock.patch('controller.patch_crd_annotations')
    def test_user_not_found(
            self,
            annotation_patch_mock,
            create_task_mock,
            get_secret,
            mock_crd_user_synched,
            k8s_client,
            user_email,
            keycloak_url,
            keycloak_realm,
            k8s_watch_mock,
            admin_token_request
        ):
        """
        Tests that the task request is not sent to the FN
        if the CRD user cannot be found in keycloak
        """
        mock_crd_user_synched['object']['spec']['user'] = {"username": user_email}
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_user_synched]

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                url=f"{keycloak_url}/admin/realms/{keycloak_realm}/users?username={user_email}&exact=true",
                status=200,
                json=[]
            )
            rsps.add(admin_token_request)
            start(True)

        annotation_patch_mock.assert_not_called()
        create_task_mock.assert_not_called()

    @mock.patch('controller.create_task')
    @mock.patch('controller.patch_crd_annotations')
    def test_no_user_provided_in_crd(
            self,
            annotation_patch_mock,
            create_task_mock,
            mock_crd_user_synched,
            k8s_client,
            k8s_watch_mock,
        ):
        """
        Tests that the task request is not sent to the FN
        if the CRD does not have any user info
        """
        mock_crd_user_synched['object']['spec']['user'] = {}
        k8s_watch_mock.return_value.stream.return_value = [mock_crd_user_synched]

        start(True)

        annotation_patch_mock.assert_not_called()
        create_task_mock.assert_not_called()