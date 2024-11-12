"""
Kubernetes controller to handle the Custom Resource Definition Analytics
The goal is simple, all new CRDs should trigger a new task on the FN.
"""
from copy import deepcopy
import logging
import traceback
import re
import urllib3
from kubernetes.watch import Watch
from kubernetes.client.exceptions import ApiException

from const import DOMAIN, TASK_NAMESPACE
from excpetions import FederatedNodeException, KeycloakException
from helpers.kubernetes_helper import (
    v1_custom_objects, k8s_config, patch_crd_annotations, create_helper_job
)
from helpers.pod_watcher import watch_task_pod, watch_user_pod
from helpers.task_helper import create_task, get_user_token

logging.basicConfig()
logger = logging.getLogger('controller')
logger.setLevel(logging.INFO)

k8s_config()


def create_labels(crds:dict) -> dict:
    """
    Given the crd spec dictionary, creates a dictionary
    to be used as a labels set. Trims each field to
    64 chars as that's k8s limit
    """
    labels = deepcopy(crds)
    labels["dataset"] = str(labels["dataset"])[:63]
    labels.update(labels.pop("user"))
    labels["repository"] = labels["repository"].replace("/", "-")[:63]
    labels["image"] = re.sub(r'(\/|:)', '-', labels["image"])[:63]
    return labels


def start(exit_on_tests=False):
    """
    Effectively the entrypoint of the controller.
    Accepts the `exit_on_tests` argument which is mostly,
    as the name suggests, used for tests and has to be explicitly
    set via a code change rather than an env var
    """
    watcher = Watch()
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
                labels = create_labels(crds["object"]["spec"])

                # should trigger the user check
                create_helper_job(
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
                watch_task_pod(
                    crd_name,
                    crds["object"]["spec"],
                    annotations[f"{DOMAIN}/task_id"],
                    get_user_token(user),
                    annotations
                )

            if exit_on_tests:
                watcher.stop()
                break
        except urllib3.exceptions.MaxRetryError as mre:
            # in case of unreachable URLs we want to fail and exit
            logger.error(mre.reason)
            raise mre
        except (KeycloakException, FederatedNodeException, ApiException) as ke:
            logger.error(ke.reason)
        except KeyError:
            # Possibly missing values, it shouldn't crash the pod
            logger.error(traceback.format_exc())
        # pylint: disable=W0718
        except Exception:
            logger.error("Unknown error: %s", traceback.format_exc())
