"""
K8s helpers functions
    - set the configuration
    - fetch a secret and decode a given key
"""

import os
import base64
import logging
from kubernetes import client, config
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
