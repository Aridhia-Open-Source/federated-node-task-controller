import pytest
from kubernetes.client.exceptions import ApiException
from unittest import mock
from const import HELPER_IMAGE
from models.crd import MAX_RETRIES
from controller import start
from exceptions import KubernetesException
from helpers.kubernetes_helper import KubernetesV1Batch


class TestKubernetesHelper:
    @pytest.mark.asyncio
    async def test_job_pv_creation_exists(
        self,
        k8s_client,
        k8s_watch_mock,
        mock_job_watch,
        delivery_open
    ):
        """
        Tests the first step of the CRD lifecycle.
        If the kubernetes PV can't be created it will not progress
        the CRD in its cycle
        """
        k8s_client["create_persistent_volume_mock"].side_effect = ApiException(status=409)
        await start(True)
        k8s_client["create_namespaced_job_mock"].assert_called()
        k8s_client["patch_cluster_custom_object_mock"].assert_called()

    @pytest.mark.asyncio
    async def test_job_pv_creation_fails(
        self,
        k8s_client,
        k8s_watch_mock,
        job_spec_mock,
        mock_job_watch,
        delivery_open,
        mocker
    ):
        """
        Tests the first step of the CRD lifecycle.
        If the kubernetes PV can't be created it will not progress
        the CRD in its cycle
        """
        mocker.patch(
            'helpers.kubernetes_helper.KubernetesV1Batch.create_retry_job'
        )
        k8s_client["create_persistent_volume_mock"].side_effect = ApiException('Error')
        await start(True)
        k8s_client["create_namespaced_job_mock"].assert_not_called()
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()

    @pytest.mark.asyncio
    async def test_job_creation_fails(
        self,
        k8s_client,
        k8s_watch_mock,
        mock_job_watch,
        delivery_open,
        mocker
    ):
        """
        Tests the first step of the CRD lifecycle.
        If the kubernetes user sync job can't be created it will not progress
        the CRD in its cycle
        """
        mocker.patch(
            'helpers.kubernetes_helper.KubernetesV1Batch.create_retry_job'
        )
        k8s_client["create_namespaced_job_mock"].side_effect = ApiException(http_resp=mock.Mock(data=""))
        await start(True)
        k8s_client["patch_cluster_custom_object_mock"].assert_not_called()

    @pytest.mark.asyncio
    @mock.patch('controller.sync_users')
    @mock.patch('helpers.actions.KubernetesV1Batch.create_bare_job')
    async def test_on_crd_exceptions_create_retry_job(
            self,
            create_bare_job_mock,
            sync_mock,
            k8s_client,
            k8s_watch_mock,
            mock_job_watch,
        ):
        """
        When an exception occurs during the CRD lifecycle
        it should be put back in a retry queue with an
        exponential cooldown
        """
        crd_name = k8s_watch_mock.return_value.stream.return_value[0]["object"]["metadata"]["name"]
        sync_mock.side_effect=KubernetesException('Error')
        await start(True)
        create_bare_job_mock.assert_called_with(
            **{
                "name": f"update-annotation-{crd_name}",
                "command": "sleep 2 && " \
                    f"kubectl annotate --overwrite analytics {crd_name} tasks.federatednode.com/tries=1",
                "run": True,
                "labels": {
                    "cooldown": "2s",
                    "crd": crd_name
                },
                "image": HELPER_IMAGE}
        )

    @pytest.mark.asyncio
    @mock.patch('controller.sync_users')
    @mock.patch('helpers.actions.KubernetesV1Batch.create_bare_job')
    async def test_on_crd_exceptions_doesnt_create_retry_job_if_another_is_running(
            self,
            create_bare_job_mock,
            sync_mock,
            k8s_client,
            k8s_watch_mock,
            mock_job_watch,
        ):
        """
        When an exception occurs during the CRD lifecycle
        it should be put back in a retry queue with an
        exponential cooldown. This should not be done, if another
        update annotation job is in progress for the same CRD
        """
        sync_mock.side_effect=KubernetesException('Error')
        k8s_client["list_namespaced_pod"].return_value.items = [mock.Mock()]
        await start(True)

        create_bare_job_mock.assert_not_called()

    @pytest.mark.asyncio
    @mock.patch('controller.sync_users')
    @mock.patch('helpers.actions.KubernetesV1Batch.create_bare_job')
    async def test_on_crd_exceptions_create_retry_job_max_retries(
            self,
            create_bare_job_mock,
            sync_mock,
            k8s_client,
            k8s_watch_mock,
            mock_job_watch
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

        await start(True)
        create_bare_job_mock.assert_not_called()


class TestHelperJobVolumeMounts:
    def _build_helper_job(self, mocker, monkeypatch, aws_enabled=False):
        mocker.patch('helpers.kubernetes_helper.KubernetesV1.create_persistent_volume')
        mocker.patch('helpers.kubernetes_helper.KubernetesV1.create_namespaced_persistent_volume_claim')
        create_job_mock = mocker.patch(
            'helpers.kubernetes_helper.KubernetesV1Batch.create_namespaced_job'
        )

        monkeypatch.delenv('AWS_STORAGE_ENABLED', raising=False)
        if aws_enabled:
            monkeypatch.setenv('AWS_STORAGE_ENABLED', 'true')
            monkeypatch.setenv('AWS_STORAGE_DRIVER', 'efs.csi.aws.com')
            monkeypatch.setenv('AWS_FILES_SYSTEM_ID', 'fs-12345678')

        KubernetesV1Batch().create_helper_job(
            name="task-89-results",
            task_id="89",
            crd_name="mvp-code-test",
            user={"username": "testuser"}
        )
        return create_job_mock

    def _results_mount(self, create_job_mock):
        job_body = create_job_mock.call_args.kwargs['body']
        vol_mounts = job_body.spec.template.spec.containers[0].volume_mounts
        return next(m for m in vol_mounts if m.name == "results")

    def _git_volume(self, create_job_mock):
        job_body = create_job_mock.call_args.kwargs['body']
        volumes = job_body.spec.template.spec.volumes
        return next(v for v in volumes if v.name == "git")

    def _git_mount(self, create_job_mock):
        job_body = create_job_mock.call_args.kwargs['body']
        vol_mounts = job_body.spec.template.spec.containers[0].volume_mounts
        return next(m for m in vol_mounts if m.name == "git")

    def test_results_mount_always_uses_controller_subpath(self, mocker, monkeypatch):
        create_job_mock = self._build_helper_job(mocker, monkeypatch)
        assert self._results_mount(create_job_mock).sub_path == "controller"

    def test_aws_results_mount_uses_controller_subpath(self, mocker, monkeypatch):
        create_job_mock = self._build_helper_job(mocker, monkeypatch, aws_enabled=True)
        assert self._results_mount(create_job_mock).sub_path == "controller"

    def test_git_volume_is_empty_dir(self, mocker, monkeypatch):
        create_job_mock = self._build_helper_job(mocker, monkeypatch)
        git_vol = self._git_volume(create_job_mock)
        assert git_vol.empty_dir is not None

    def test_git_mount_path_is_mnt_git(self, mocker, monkeypatch):
        create_job_mock = self._build_helper_job(mocker, monkeypatch)
        assert self._git_mount(create_job_mock).mount_path == "/mnt/git/"

    def test_repo_folder_env_uses_git_mount(self, mocker, monkeypatch):
        create_job_mock = self._build_helper_job(mocker, monkeypatch)
        job_body = create_job_mock.call_args.kwargs['body']
        env = job_body.spec.template.spec.containers[0].env
        repo_folder = next(e for e in env if e.name == "REPO_FOLDER")
        assert repo_folder.value.startswith("/mnt/git/")
