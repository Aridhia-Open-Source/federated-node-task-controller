import os
import logging
from kubernetes import client
from kubernetes.config import load_kube_config, load_incluster_config


logger = logging.getLogger('migrate_crd')
logger.setLevel(logging.INFO)

CRD_GROUP = os.getenv("CRD_GROUP")

if 'KUBERNETES_PORT' in os.environ:
    load_incluster_config()
else:
    load_kube_config()

k8s = client.CustomObjectsApi()

def patch_crd_status(crd_name:str, status: dict):
    """
    Since it's too verbose, and has to get a "patch" dedicated to it
    the annotation update is done here.
    """
    # Patch for the client library which somehow doesn't do it itself for the patch
    k8s.api_client.set_default_header('Content-Type', 'application/merge-patch+json')
    k8s.patch_cluster_custom_object_status(
        CRD_GROUP, "v2", "analytics", crd_name, {"status": status}
    )
    logger.info("CRD status patched")

def patch_crd(crd:dict):
    """
    Since it's too verbose, and has to get a "patch" dedicated to it
    the annotation update is done here.
    """
    # Patch for the client library which somehow doesn't do it itself for the patch
    k8s.api_client.set_default_header('Content-Type', 'application/merge-patch+json')
    k8s.patch_cluster_custom_object(
        CRD_GROUP, "v2", "analytics", crd["metadata"]["name"], crd
    )
    logger.info("CRD patched")

for crd in k8s.list_cluster_custom_object(
    CRD_GROUP,
    "v1",
    "analytics",
    pretty=True
)["items"]:
    logging.info("Patching %s ...", crd["metadata"]["name"])
    crd["apiVersion"] = f"{CRD_GROUP}/v2"
    status = {}
    for key,val in crd["metadata"]["annotations"].items():
        if key == f"{CRD_GROUP}/user":
            status["userMigrated"] = True
        elif key == f"{CRD_GROUP}/task_id":
            status["taskID"] = int(val)
        elif key == f"{CRD_GROUP}/results":
            status["resultsDelivered"] = True
        elif key == f"{CRD_GROUP}/approved":
            status["approved"] = True
        elif key == f"{CRD_GROUP}/tries":
            status["retries"] = int(val)

    patch_crd(crd)
    patch_crd_status(crd["metadata"]["name"], status)
    logging.info("Done")

logging.info("All migrated. Exiting")
