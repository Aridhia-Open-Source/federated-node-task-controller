"""
Kubernetes controller to handle the Custom Resource Definition Analytics
The goal is simple, all new CRDs should trigger a new task on the FN.
"""

from copy import deepcopy
import logging
import traceback
import re
import urllib3
from kubernetes import watch
from kubernetes.client.exceptions import ApiException

from .const import DOMAIN, TASK_NAMESPACE, NAMESPACE
from .excpetions import FederatedNodeException, KeycloakException
from controller.helpers.kubernetes_helper import v1, v1_custom_objects, k8s_config, patch_crd_annotations, create_job_push_results
from controller.helpers.task_helper import create_task, get_results, get_user_token

logging.basicConfig()
logger = logging.getLogger('controller')
logger.setLevel(logging.INFO)

k8s_config()

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
            if pod["object"].status.phase == "Succeeded":
                get_results(task_id, user_token)
                create_job_push_results(
                    name=f"task-{task_id}-results",
                    task_id=task_id,
                    repository=repository
                )
                # Add results annotation to let the controller know
                # we already handled results
                patch_crd_annotations(crd_name, annotations)
                break
            else:
                logger.info("Pod still running. Status: %s",  pod["object"].status.phase)
    logger.info(f"Stopping task {task_id} pod watcher")
    pod_watcher.stop()

def watch_user_pod(crd_name:str, user:str, labels:dict, annotations:dict):
    """
    Given a task id, checks for active pods with
    task_id label, and once completed, trigger the results fetching
    """
    pod_watcher = watch.Watch()
    ls = ",".join(f"{lab[0]}={lab[1]}" for lab in labels.items())
    for pod in pod_watcher.stream(
        v1.list_namespaced_pod,
        NAMESPACE,
        label_selector=ls,
        resource_version='',
        watch=True
        ):
            logger.info("Found pod! %s", pod["object"].metadata.name)
            if pod["object"].status.phase == "Succeeded":
                # Add results annotation to let the controller know
                # we already handled the user
                patch_crd_annotations(crd_name, annotations)
                break
            else:
                logger.info("Pod still running. Status: %s", pod["object"].status.phase)
    logger.info(f"Stopping {" ".join(user.values())} pod watcher")
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
        dataset=crds["object"]["spec"].get("dataset")

        if crds["type"] == "DELETED" or crds["object"]["metadata"].get("deletionTimestamp"):
            continue

        if crds["type"] == "ADDED" and not annotations.get(f"{DOMAIN}/user"):
            labels = deepcopy(crds["object"]["spec"])
            labels["dataset"] = str(labels["dataset"])
            labels.update(labels.pop("user"))
            labels["repository"] = labels["repository"].replace("/", "-")
            labels["image"] = re.sub(r'(\/|:)', '-', labels["image"])

            # should trigger the user check
            create_job_push_results(
                f"link-user-{"".join(user.values())}",
                script="init_container.sh",
                create_volumes=False,
                labels=labels,
                repository=crds["object"]["spec"].get("repository")
            )

            annotations[f"{DOMAIN}/user"] = "ok"

            watch_user_pod(crd_name, user, labels, annotations)
        elif annotations.get(f"{DOMAIN}/user") and not annotations.get(f"{DOMAIN}/done"):
            user_token = get_user_token(user)
            logger.info("Creating task with image %s", image)

            task_resp = create_task(
                image,
                crd_name,
                proj_name,
                dataset,
                user_token
            )

            annotations[f"{DOMAIN}/done"] = "true"
            if "task_id" in task_resp:
                annotations[f"{DOMAIN}/task_id"] = str(task_resp["task_id"])
            patch_crd_annotations(crd_name, annotations)

        elif annotations.get(f"{DOMAIN}/done") and not annotations.get(f"{DOMAIN}/results"):
            # If we have already triggered a task, check if the pod has completed
            annotations[f"{DOMAIN}/results"] = "true"
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
