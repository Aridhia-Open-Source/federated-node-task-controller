"""
K8s helpers functions
    - set the configuration
    - fetch a secret and decode a given key
"""

import os
import base64
import logging
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from controller.excpetions import KubernetesException
from controller.const import DOMAIN, NAMESPACE

def k8s_config():
    """
    Configure the k8s client, if KUBERNETES_PORT
    is in the env, means we are on a cluster, otherwise
    load_kube_config will look into ~/.kube
    """
    if 'KUBERNETES_PORT' in os.environ:
        config.load_incluster_config()
    else:
        config.load_kube_config()

logger = logging.getLogger('helpers')
logger.setLevel(logging.INFO)

k8s_config()

v1 = client.CoreV1Api()
v1_batch = client.BatchV1Api()


def get_secret(name:str, key:str, namespace:str="default") -> str:
    """
    Returns a secret decoded value from a secret name, and its key
    """
    secret = v1.read_namespaced_secret(name, namespace)
    return base64.b64decode(secret.data[key].encode()).decode()


def patch_crd_annotations(name:str, annotations:dict):
    """
    Since it's too verbose, and has to get a "patch" dedicated to it
    the annotation update is done here.
    """
    v1_custom_objects = client.CustomObjectsApi()
    # Patch for the client library which somehow doesn't do it itself for the patch
    v1_custom_objects.api_client.set_default_header('Content-Type', 'application/json-patch+json')
    v1_custom_objects.patch_namespaced_custom_object(
        DOMAIN, "v1", NAMESPACE, "analytics", name,
        [{"op": "add", "path": "/metadata/annotations", "value": annotations}]
    )


def setup_pv(name:str):
    pv_spec = client.V1PersistentVolumeSpec(
        access_modes=['ReadWriteMany'],
        capacity={"storage": "100Mi"},
        storage_class_name="shared-results",
        host_path=client.V1HostPathVolumeSource(
            path="/data/controller"
        )
    )
    # pv = client.V1PersistentVolume(
    #     api_version='v1',
    #     kind='PersistentVolume',
    #     metadata=client.V1ObjectMeta(name=name, namespace=NAMESPACE),
    #     spec=pv_spec
    # )
    # try:
    #     v1.create_persistent_volume(body=pv)
    # except ApiException as kexc:
    #     if kexc.status != 409:
    #         raise KubernetesException(kexc.body)

    pvc = client.V1PersistentVolumeClaim(
        api_version='v1',
        kind='PersistentVolumeClaim',
        metadata=client.V1ObjectMeta(name=f"{name}-volclaim", namespace=NAMESPACE),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=['ReadWriteMany'],
            volume_name="controller-pv",
            storage_class_name="shared-results",
            resources=client.V1VolumeResourceRequirements(requests={"storage": "100Mi"})
        )
    )
    try:
        v1.create_namespaced_persistent_volume_claim(body=pvc, namespace=NAMESPACE)
    except ApiException as kexc:
        if kexc.status != 409:
            raise KubernetesException(kexc.body)


def create_job_push_results(
        name:str, task_id:str,
        organization="Aridhia-Open-Source",
        repository="Federated-Node-Example-App"
    ):
    """
    Creates the job template and submits it to the cluster in the
    same namespace as the controller's
    """
    setup_pv(name)
    volumes = [
        client.V1Volume(
            name="results",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(claim_name=f"{name}-volclaim")
        ),
        client.V1Volume(
            name="key",
            secret=client.V1SecretVolumeSource(
                secret_name="ghpk",
                items=[client.V1KeyToPath(key="key.pem", path="key.pem")]
            )
        )
    ]
    vol_mounts = [
        client.V1VolumeMount(
            mount_path="/mnt/results/",
            name="results"
        ),
        client.V1VolumeMount(
            mount_path="/mnt/key/",
            name="key"
        )
    ]
    container = client.V1Container(
        name=name,
        image="custom_controller:0.0.1",
        volume_mounts=vol_mounts,
        command=["/bin/sh", "/app/scripts/push_to_github.sh"],
        env=[
            client.V1EnvVar(name="KEY_FILE", value="/mnt/key/key.pem"),
            client.V1EnvVar(name="TASK_ID", value=task_id),
            client.V1EnvVar(name="GH_ORGANIZATION", value=organization),
            client.V1EnvVar(name="GH_REPO", value=repository),
            client.V1EnvVar(name="REPO_FOLDER", value=f"/mnt/results/{name}"),
        ],
        env_from=[
            client.V1EnvFromSource(secret_ref=client.V1SecretEnvSource(name="gh-client-id"))
        ]
    )

    metadata = client.V1ObjectMeta(
        name=name,
        namespace=NAMESPACE
    )
    specs = client.V1PodSpec(
        containers=[container],
        restart_policy="Never",
        volumes=volumes
    )
    template = client.V1JobTemplateSpec(
        metadata=metadata,
        spec=specs
    )
    specs = client.V1JobSpec(
        template=template,
        ttl_seconds_after_finished=5
    )
    try:
        v1_batch.create_namespaced_job(
            namespace=NAMESPACE,
            body=client.V1Job(
                api_version='batch/v1',
                kind='Job',
                metadata=metadata,
                spec=specs
            ),
            pretty=True
        )
    except ApiException as e:
        raise KubernetesException(e.body)
