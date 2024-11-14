from kubernetes.client.exceptions import ApiException
from unittest import mock
from const import NAMESPACE, MAX_RETRIES
from controller import start
from excpetions import KubernetesException


class TestKubernetesHelper:
    def test_job_pv_creation_exists(
        self,
        k8s_client,
        k8s_watch_mock,
        mock_pod_watch
    ):
        """
        Tests the first step of the CRD lifecycle.
        If the kubernetes PV can't be created it will not progress
        the CRD in its cycle
        """
        k8s_client["kh_v1_client"].create_persistent_volume.side_effect = ApiException(status=409)
        start(True)
        k8s_client["kh_v1_batch_client"].create_namespaced_job.assert_called()
        annotation_patch_mock = k8s_client["kh_v1_crd_client"].patch_namespaced_custom_object
        annotation_patch_mock.assert_called()

    @mock.patch('controller.create_retry_job')
    def test_job_pv_creation_fails(
        self,
        create_bare_job_mock,
        k8s_client,
        k8s_watch_mock,
        job_spec_mock
    ):
        """
        Tests the first step of the CRD lifecycle.
        If the kubernetes PV can't be created it will not progress
        the CRD in its cycle
        """
        k8s_client["kh_v1_client"].create_persistent_volume.side_effect = ApiException()
        start(True)
        k8s_client["kh_v1_batch_client"].create_namespaced_job.assert_not_called()
        annotation_patch_mock = k8s_client["kh_v1_crd_client"].patch_namespaced_custom_object
        annotation_patch_mock.assert_not_called()

    @mock.patch('controller.create_retry_job')
    def test_job_creation_fails(
        self,
        create_bare_job_mock,
        k8s_client,
        k8s_watch_mock,
        mock_pod_watch
    ):
        """
        Tests the first step of the CRD lifecycle.
        If the kubernetes user sync job can't be created it will not progress
        the CRD in its cycle
        """
        k8s_client["kh_v1_batch_client"].create_namespaced_job.side_effect = ApiException(http_resp=mock.Mock(data=""))
        start(True)
        annotation_patch_mock = k8s_client["kh_v1_crd_client"].patch_namespaced_custom_object
        annotation_patch_mock.assert_not_called()

    @mock.patch('controller.sync_users')
    @mock.patch('helpers.actions.create_bare_job')
    def test_on_crd_exceptions_create_retry_job(
            self,
            create_bare_job_mock,
            sync_mock,
            k8s_client,
            k8s_watch_mock,
            mock_pod_watch,
        ):
        """
        When an exception occurs during the CRD lifecycle
        it should be put back in a retry queue with an
        exponential cooldown
        """
        crd_name = k8s_watch_mock.return_value.stream.return_value[0]["object"]["metadata"]["name"]
        sync_mock.side_effect=KubernetesException('Error')
        start(True)
        create_bare_job_mock.assert_called_with(
            f"update-annotation-{crd_name}",
            **{
                "command": "sleep 2 && " \
                        f"kubectl get analytics -n analytics {crd_name} -o json |"\
                        " jq '.metadata.annotations += {\"tasks.federatednode.com/tries\": \"1\"}' | "\
                        "kubectl replace -f-",
                "run": True,
                "labels": {
                    "cooldown": "2s",
                    "crd": crd_name
                },
                "image": "alpine/k8s:1.29.4"}
        )

    @mock.patch('controller.sync_users')
    @mock.patch('helpers.actions.create_bare_job')
    def test_on_crd_exceptions_create_retry_job_max_retries(
            self,
            create_bare_job_mock,
            sync_mock,
            k8s_client,
            k8s_watch_mock,
            mock_pod_watch
        ):
        """
        When an exception occurs during the CRD lifecycle
        it should be put back in a retry queue with an
        exponential cooldown only if it doesn't exceed the max
        number of retries
        """
        k8s_watch_mock.return_value.stream.return_value[0]\
            ["object"]["metadata"]["annotations"] \
                ["tasks.federatednode.com/tries"] = MAX_RETRIES + 1

        sync_mock.side_effect=KubernetesException('Error')
        start(True)
        create_bare_job_mock.assert_not_called()
