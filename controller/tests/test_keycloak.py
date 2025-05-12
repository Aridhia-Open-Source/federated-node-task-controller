import pytest
import responses
from unittest import mock
from controller import start
from excpetions import CRDException


class TestKeycloakRequests:
    def test_user_auth_fails(
            self,
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

        annotation_patch_mock = k8s_client["patch_cluster_custom_object_mock"].patch_cluster_custom_object
        annotation_patch_mock.assert_not_called()

    def test_email_provided_in_crd(
            self,
            mock_crd_user_synched,
            crd_name,
            k8s_client,
            user_email,
            keycloak_url,
            keycloak_realm,
            k8s_watch_mock,
            admin_token_request,
            impersonate_request,
            fn_task_request,
            domain
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

    def test_username_provided_in_crd(
            self,
            mock_crd_user_synched,
            crd_name,
            k8s_client,
            user_email,
            keycloak_url,
            keycloak_realm,
            k8s_watch_mock,
            admin_token_request,
            impersonate_request,
            fn_task_request,
            domain
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

    @mock.patch('helpers.actions.create_task')
    def test_user_not_found(
            self,
            create_task_mock,
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

        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()
        create_task_mock.assert_not_called()

    @mock.patch('helpers.actions.create_task')
    def test_no_user_provided_in_crd(
            self,
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

        with pytest.raises(CRDException):
            start(True)

        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()
        create_task_mock.assert_not_called()
