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
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from excpetions import KubernetesException
from const import (
    DOMAIN, NAMESPACE, TASK_NAMESPACE, IMAGE,
    MOUNT_PATH, PULL_POLICY, TAG, KC_USER
)

base_label = {
    f"{DOMAIN}": "fn-controller"
}

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

logger = logging.getLogger('k8s_helpers')
logger.setLevel(logging.INFO)

k8s_config()

v1 = client.CoreV1Api()
v1_batch = client.BatchV1Api()
v1_custom_objects = client.CustomObjectsApi()

def get_secret(name:str, key:str, namespace:str=NAMESPACE) -> str:
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
    # Patch for the client library which somehow doesn't do it itself for the patch
    v1_custom_objects.api_client.set_default_header('Content-Type', 'application/json-patch+json')
    v1_custom_objects.patch_namespaced_custom_object(
        DOMAIN, "v1", TASK_NAMESPACE, "analytics", name,
        [{"op": "add", "path": "/metadata/annotations", "value": annotations}]
    )
    logger.info("CRD patched")


def setup_pvc(name:str) -> str:
    """
    Create a pvc and returns the name
    """
    pv_name = f"{name}-pv"
    pers_vol = client.V1PersistentVolume(
            api_version='v1',
            kind='PersistentVolume',
            metadata=client.V1ObjectMeta(
                name=pv_name, namespace=NAMESPACE,
                labels=base_label
            ),
            spec=client.V1PersistentVolumeSpec(
                access_modes=['ReadWriteMany'],
                capacity={"storage": "100Mi"},
                storage_class_name="controller-results",
                host_path=client.V1HostPathVolumeSource(path=MOUNT_PATH),
                persistent_volume_reclaim_policy="Delete"
            )
        )

    volclaim_name = f"{name}-volclaim"
    pvc = client.V1PersistentVolumeClaim(
        api_version='v1',
        kind='PersistentVolumeClaim',
        metadata=client.V1ObjectMeta(
            name=volclaim_name, namespace=NAMESPACE,
            labels=base_label,
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
        v1.create_persistent_volume(body=pers_vol)
    except ApiException as kexc:
        if kexc.status != 409:
            raise KubernetesException(kexc.body) from kexc
    try:
        v1.create_namespaced_persistent_volume_claim(body=pvc, namespace=NAMESPACE)
    except ApiException as kexc:
        if kexc.status != 409:
            raise KubernetesException(kexc.body) from kexc
    return volclaim_name

def repo_secret_name(repository:str):
    """
    Standardization for a secret name from a org/repo string
    """
    return re.sub(r'[\W_]+', '-', repository.lower())

def create_helper_job(
        name:str, task_id:str=None,
        repository="Federated-Node-Example-App",
        create_volumes:bool=True,
        script:str="push_to_github.sh", labels:dict={}
    ):
    """
    Creates the job template and submits it to the cluster in the
    same namespace as the controller's
    """
    volclaim_name = setup_pvc(name)
    secret_name=repo_secret_name(repository)
    name += f"-{uuid4()}"
    name = name[:62]
    labels.update(base_label)

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
        client.V1EnvVar(name="KC_HOST", value="http://keycloak.identities.svc.cluster.local"),
        client.V1EnvVar(name="KC_USER", value=KC_USER),
        client.V1EnvVar(name="KEY_FILE", value="/mnt/key/key.pem"),
        client.V1EnvVar(name="GH_REPO", value=repository),
        client.V1EnvVar(name="REPO_FOLDER", value=f"/mnt/results/{name}"),
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
    container = client.V1Container(
        name=name,
        image_pull_policy=PULL_POLICY,
        image=f"{IMAGE}:{TAG}",
        volume_mounts=vol_mounts,
        command=["/bin/sh", f"/app/scripts/{script}"],
        env=env
    )

    metadata = client.V1ObjectMeta(
        name=name,
        namespace=NAMESPACE,
        labels=labels
    )
    specs = client.V1PodSpec(
        containers=[container],
        restart_policy="OnFailure",
        volumes=volumes,
        image_pull_secrets=[client.V1LocalObjectReference("regcred")]
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
    except ApiException as exc:
        raise KubernetesException(exc.body) from exc
