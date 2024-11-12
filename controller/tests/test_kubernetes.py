from kubernetes.client.exceptions import ApiException
from unittest import mock
from controller import start


class TestKubernetesHelper:
    @mock.patch('helpers.pod_watcher.patch_crd_annotations')
    def test_job_pv_creation_exists(
        self,
        annotation_patch_mock,
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
        annotation_patch_mock.assert_called()

    @mock.patch('controller.patch_crd_annotations')
    def test_job_pv_creation_fails(
        self,
        annotation_patch_mock,
        k8s_client,
        k8s_watch_mock,
        mock_pod_watch
    ):
        """
        Tests the first step of the CRD lifecycle.
        If the kubernetes PV can't be created it will not progress
        the CRD in its cycle
        """
        k8s_client["kh_v1_client"].create_persistent_volume.side_effect = ApiException()
        start(True)
        k8s_client["kh_v1_batch_client"].create_namespaced_job.assert_not_called()
        annotation_patch_mock.assert_not_called()

    @mock.patch('controller.patch_crd_annotations')
    def test_job_creation_fails(
        self,
        annotation_patch_mock,
        k8s_client,
        k8s_watch_mock,
        mock_pod_watch
    ):
        """
        Tests the first step of the CRD lifecycle.
        If the kubernetes user sync job can't be created it will not progress
        the CRD in its cycle
        """
        k8s_client["kh_v1_client"].create_namespaced_job.side_effect = ApiException()
        start(True)
        annotation_patch_mock.assert_not_called()
