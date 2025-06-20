"""
K8s helpers functions
    - set the configuration
    - fetch a secret and decode a given key
"""

import os
import re
import base64
import logging

from uuid import uuid4
from kubernetes import client
from kubernetes.config import load_kube_config, load_incluster_config
from kubernetes.client.exceptions import ApiException

from exceptions import KubernetesException
from const import (
    NAMESPACE, IMAGE, MOUNT_PATH,
    PULL_POLICY, TAG, KC_USER, KC_HOST, TASK_NAMESPACE
)
from models.crd import Analytics

logger = logging.getLogger('k8s_helpers')
logger.setLevel(logging.INFO)


class BaseK8s:
    """
    Base k8s client to handle credentials for child classes
    """
    base_label = {
        f"{Analytics.domain}": "fn-controller"
    }
    def __init__(self, **kwargs):
        """
        Configure the k8s client, if KUBERNETES_PORT
        is in the env, means we are on a cluster, otherwise
        load_kube_config will look into ~/.kube
        """
        if 'KUBERNETES_PORT' in os.environ:
            load_incluster_config()
        else:
            load_kube_config()
        super().__init__(**kwargs)

    def repo_secret_name(self, repository:str):
        """
        Standardization for a secret name from a org/repo string
        """
        return re.sub(r'[\W_]+', '-', repository.lower())


class KubernetesCRD(BaseK8s, client.CustomObjectsApi):
    """
    Custom k8s client wrapper to handle CRD operations
    """
    def patch_crd_annotations(self, name:str, annotations:dict):
        """
        Since it's too verbose, and has to get a "patch" dedicated to it
        the annotation update is done here.
        """
        # Patch for the client library which somehow doesn't do it itself for the patch
        self.api_client.set_default_header('Content-Type', 'application/json-patch+json')
        self.patch_cluster_custom_object(
            Analytics.domain, "v1", "analytics", name,
            [{"op": "add", "path": "/metadata/annotations", "value": annotations}]
        )
        logger.info("CRD patched")


class KubernetesV1(BaseK8s, client.CoreV1Api):
    """
    Custom k8s client wrapper to centralized common
    operations on top of the base client
    """
    def get_secret(self, name:str, key:str, namespace:str=NAMESPACE) -> str:
        """
        Returns a secret decoded value from a secret name, and its key
        """
        secret = self.read_namespaced_secret(name, namespace)
        return base64.b64decode(secret.data[key].encode()).decode()

    def get_secret_by_label(self, label:str, namespace:str=NAMESPACE):
        """
        Gets the list of secrets with the label, and return the first match
        """
        secrets_list = self.list_namespaced_secret(namespace=namespace, label_selector=label)
        if not secrets_list:
            raise KubernetesException(f"No secrets found with label(s) {label}")

        return secrets_list.items[0]

    def setup_pvc(self, name:str) -> str:
        """
        Create a pvc and returns the name
        """
        pv_name = f"{name}-pv"
        pv_spec = client.V1PersistentVolumeSpec(
            access_modes=['ReadWriteMany'],
            capacity={"storage": "100Mi"},
            storage_class_name="controller-results"
        )
        if os.getenv("AZURE_STORAGE_ENABLED"):
            pv_spec.azure_file = client.V1AzureFilePersistentVolumeSource(
                read_only=False,
                secret_name=os.getenv("AZURE_SECRET_NAME"),
                share_name=os.getenv("AZURE_SHARE_NAME")
            )
        else:
            pv_spec.host_path = client.V1HostPathVolumeSource(
                path=f"{MOUNT_PATH}/controller/"
            )

        pers_vol = client.V1PersistentVolume(
            api_version='v1',
            kind='PersistentVolume',
            metadata=client.V1ObjectMeta(name=pv_name, namespace=TASK_NAMESPACE),
            spec=pv_spec
        )

        volclaim_name = f"{name}-volclaim"
        pvc = client.V1PersistentVolumeClaim(
            api_version='v1',
            kind='PersistentVolumeClaim',
            metadata=client.V1ObjectMeta(
                name=volclaim_name, namespace=NAMESPACE,
                labels=self.base_label,
                annotations={"kubernetes.io/pvc.recyclePolicy": "Delete"}
            ),
            spec=client.V1PersistentVolumeClaimSpec(
                access_modes=['ReadWriteMany'],
                volume_name=pv_name,
                storage_class_name="controller-results",
                resources=client.V1VolumeResourceRequirements(requests={"storage": "100Mi"})
            )
        )
        try:
            self.create_persistent_volume(body=pers_vol)
        except ApiException as kexc:
            if kexc.status != 409:
                raise KubernetesException(kexc.body) from kexc
        try:
            self.create_namespaced_persistent_volume_claim(body=pvc, namespace=NAMESPACE)
        except ApiException as kexc:
            if kexc.status != 409:
                raise KubernetesException(kexc.body) from kexc
        return volclaim_name


class KubernetesV1Batch(BaseK8s, client.BatchV1Api):
    """
    Custom k8s batch client wrapper to centralized common
    operations on top of the base client
    """
    #pylint: disable=R0913
    def create_bare_job(
            self,
            name:str,
            run:bool=False,
            script:str=None,
            labels:dict=None,
            command:str=None,
            image:str=None
        ) -> client.V1Job:
        """
        Creates the job template and submits it to the cluster in the
        same namespace as the controller's
        """
        name += f"-{uuid4()}"
        name = name[:62]
        if labels is None:
            labels = {}
        labels.update(self.base_label)

        if command:
            command = ["/bin/sh", "-c", command]
        elif script:
            command = ["/bin/sh", script]

        container = client.V1Container(
            name=name,
            image_pull_policy=PULL_POLICY,
            image=image or f"{IMAGE}:{TAG}"
        )
        if command:
            container.command = command

        metadata = client.V1ObjectMeta(
            name=name,
            namespace=NAMESPACE,
            labels=labels
        )
        specs = client.V1PodSpec(
            containers=[container],
            restart_policy="OnFailure",
            service_account_name="analytics-operator"
        )
        template = client.V1JobTemplateSpec(
            metadata=metadata,
            spec=specs
        )
        specs = client.V1JobSpec(
            template=template,
            ttl_seconds_after_finished=30
        )
        body = client.V1Job(
            api_version='batch/v1',
            kind='Job',
            metadata=metadata,
            spec=specs
        )
        if run:
            try:
                self.create_namespaced_job(
                    namespace=NAMESPACE,
                    body=body,
                    pretty=True
                )
            except ApiException as exc:
                raise KubernetesException(exc.body) from exc
        return body

    def create_helper_job(
            self,
            name:str,
            task_id:str=None,
            repository="Federated-Node-Example-App",
            create_volumes:bool=True,
            script:str=None,
            labels:dict | None=None,
            command:str=None,
            crd_name:str=None,
            user:dict=None
        ):
        """
        Creates the job template and submits it to the cluster in the
        same namespace as the controller's
        """
        base_job = self.create_bare_job(name, script=script, command=command, labels=labels)
        volclaim_name = KubernetesV1().setup_pvc(name)
        secret_name=self.repo_secret_name(repository)
        if labels is None:
            labels = {}
        labels.update(self.base_label)

        volumes = [
            client.V1Volume(
                name="key",
                secret=client.V1SecretVolumeSource(
                    secret_name=secret_name,
                    items=[client.V1KeyToPath(key="key.pem", path="key.pem")]
                )
            )
        ]

        vol_mounts = [
            client.V1VolumeMount(
                mount_path="/mnt/key/",
                name="key"
            )
        ]
        env = [
            client.V1EnvVar(name="DOMAIN", value=Analytics.domain),
            client.V1EnvVar(name="CRD_NAME", value=crd_name),
            client.V1EnvVar(name="USER_NAME", value=user.get("username")),
            client.V1EnvVar(name="KC_HOST", value=KC_HOST),
            client.V1EnvVar(name="KC_USER", value=KC_USER),
            client.V1EnvVar(name="KEY_FILE", value="/mnt/key/key.pem"),
            client.V1EnvVar(name="GH_REPO", value=repository),
            client.V1EnvVar(name="FULL_REPO", value=repository.replace("/", "-")),
            client.V1EnvVar(name="REPO_FOLDER", value=f"/mnt/results/{name}" if create_volumes else f"/apps/{name}"),
            client.V1EnvVar(name="GH_CLIENT_ID", value_from=client.V1EnvVarSource(
                secret_key_ref=client.V1SecretKeySelector(
                    name=f"{secret_name}",
                    key="GH_CLIENT_ID"
                )
            )),
            client.V1EnvVar(name="KC_PASS", value_from=client.V1EnvVarSource(
                secret_key_ref=client.V1SecretKeySelector(
                    name="kc-secrets",
                    key="KEYCLOAK_ADMIN_PASSWORD"
                )
            ))
        ]

        if task_id:
            env.append(client.V1EnvVar(name="TASK_ID", value=task_id),)

        if create_volumes:
            volumes.append(
                client.V1Volume(
                    name="results",
                    persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                        claim_name=volclaim_name
                    )
                )
            )
            vol_mounts.append(
                client.V1VolumeMount(
                    mount_path="/mnt/results/",
                    name="results"
                )
            )
        base_job.spec.template.spec.volumes = volumes
        base_job.spec.template.spec.containers[0].volume_mounts = vol_mounts
        base_job.spec.template.spec.containers[0].env = env

        try:
            self.create_namespaced_job(
                namespace=NAMESPACE,
                body=base_job,
                pretty=True
            )
        except ApiException as exc:
            raise KubernetesException(exc.body) from exc
