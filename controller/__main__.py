"""
Kubernetes controller to handle the Custom Resource Definition Analytics
The goal is simple, all new CRDs should trigger a new task on the FN.
"""

import logging
import traceback
from kubernetes import client, watch
from kubernetes.client.exceptions import ApiException
import urllib3

from .const import DOMAIN, TASK_NAMESPACE
from .excpetions import FederatedNodeException, KeycloakException
from controller.helpers.kubernetes_helpers import v1, k8s_config, patch_crd_annotations, create_job_push_results
from controller.helpers.task_helpers import create_task, get_results, get_user_token

logger = logging.getLogger('controller')
logger.setLevel(logging.INFO)

k8s_config()

v1_custom_objects = client.CustomObjectsApi()
watcher = watch.Watch()

def watch_task_pod(crd_name:str, crd_spec:dict, task_id:str, user_token:str, annotations:dict):
    """
    Given a task id, checks for active pods with
    task_id label, and once completed, trigger the results fetching
    """
    repository = crd_spec.get("repository")
    pod_watcher = watch.Watch()
    for pod in pod_watcher.stream(
        v1.list_namespaced_pod,
        TASK_NAMESPACE,
        label_selector=f"task_id={task_id}",
        resource_version='',
        watch=True
        ):
            logger.info("Found pod! %s", pod["object"].metadata.name)
            print("Found pod! " + pod["object"].metadata.name)
            if pod["object"].status.phase == "Succeeded":
                get_results(task_id, user_token)
                create_job_push_results(
                    name=f"task-{task_id}-results",
                    task_id=task_id,
                    repository=repository
                )
                # Add results annotation to let the controller know
                # we already handled results
                annotations[f"{DOMAIN}/results"] = "true"
                patch_crd_annotations(crd_name, annotations)
                break
            else:
                print("Pod still running. Status:" + pod["object"].status.phase)
    logger.info(f"Stopping task {task_id} pod watcher")
    pod_watcher.stop()

for crds in watcher.stream(
    v1_custom_objects.list_namespaced_custom_object,
    DOMAIN,
    "v1",
    TASK_NAMESPACE,
    "analytics",
    resource_version='',
    watch=True
    ):
    try:
        crd_name = crds["object"]["metadata"]["name"]
        annotations = crds["object"]["metadata"]["annotations"]
        user = crds["object"]["spec"].get("user", {})
        image = crds["object"]["spec"].get("image")
        proj_name = crds["object"]["spec"].get("project")

        if crds["type"] == "DELETED" or crds["object"]["metadata"].get("deletionTimestamp"):
            continue

        if crds["type"] == "ADDED" and not annotations.get(f"{DOMAIN}/done"):
            user_token = get_user_token(user)
            logger.info("Creating task with image %s", image)
            print(f"Creating task with image {image}")

            task_resp = create_task(
                image,
                crd_name,
                proj_name,
                crds["object"]["spec"].get("dataset"),
                user_token
            )

            annotations[f"{DOMAIN}/done"] = "true"
            if "task_id" in task_resp:
                annotations[f"{DOMAIN}/task_id"] = str(task_resp["task_id"])
            patch_crd_annotations(crd_name, annotations)

        elif annotations.get(f"{DOMAIN}/done") and not annotations.get(f"{DOMAIN}/results"):
            # If we have already triggered a task, check if the pod has completed
            watch_task_pod(crd_name, crds["object"]["spec"], annotations[f"{DOMAIN}/task_id"], get_user_token(user), annotations)

    except urllib3.exceptions.MaxRetryError as mre:
        # in case of unreachable URLs we want to fail and exit
        logger.error(mre.reason)
        raise mre
    except (KeycloakException, FederatedNodeException, ApiException) as ke:
        logger.error(ke.reason)
    except KeyError as ke:
        # Possibly missing values, it shouldn't crash the pod
        logger.error(traceback.format_exc())
    except Exception as exc:
        logger.error("Unknown error: %s", traceback.format_exc())
