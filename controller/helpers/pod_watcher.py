"""
Collection of job and pod watchers.
    - Pod watcher monitors the actual task lifecycle
    - Job watcher is mostly to focus on user sync
"""

import base64
import logging
import json
import re
import subprocess
from kubernetes.watch import Watch
from kubernetes.client.models.v1_job_status import V1JobStatus

from const import DOMAIN, TASK_NAMESPACE, NAMESPACE
from excpetions import KubernetesException, PodWatcherException
from helpers.kubernetes_helper import KubernetesV1Batch, KubernetesCRD, KubernetesV1
from helpers.request_helper import client as requests
from helpers.task_helper import get_results

logging.basicConfig()
logger = logging.getLogger('pod_watcher')
logger.setLevel(logging.INFO)


def watch_task_pod(crd_name:str, crd_spec:dict, task_id:str, user_token:str, annotations:dict):
    """
    Given a task id, checks for active pods with
    task_id label, and once completed, trigger the results fetching
    """
    delivery = json.load(open("controller/delivery.json"))
    # results_path = crd_spec.get("results", {})
    # git_info = results_path.get("git", {})
    # other_info = results_path.get("other", {})
    git_info = delivery.get("github", {})
    other_info = delivery.get("other", {})
    logger.info("Looking for pod with task_id: %s", task_id)
    pod_watcher = Watch()

    for pod in pod_watcher.stream(
        KubernetesV1().list_namespaced_pod,
        TASK_NAMESPACE,
        label_selector=f"task_id={task_id}",
        resource_version='',
        watch=True
    ):
        logger.info("Found pod! %s", pod["object"].metadata.name)
        match pod["object"].status.phase:
            case "Succeeded":
                annotations[f"{DOMAIN}/results"] = "true"
                fp = get_results(task_id, user_token)
                if git_info:
                    KubernetesV1Batch().create_helper_job(
                        name=f"task-{task_id}-results",
                        task_id=task_id,
                        repository=git_info.get("repository")
                    )
                elif other_info:
                    auth = {}
                    is_api = True

                    # Remove the http(s) from the string and use it as a label filter
                    url = re.sub(r"http(s)*://", "", other_info.get("url", ''))
                    auth_secret = KubernetesV1().get_secret_by_label(
                        namespace=NAMESPACE, label=f"url={url}"
                    )
                    creds = base64.b64decode(
                        auth_secret.data["auth"].encode()
                    ).decode()

                    match other_info.get("auth_type", '').lower():
                        case "bearer":
                            auth["headers"] = {"Authorization": f"Bearer {creds}"}
                        case "basic":
                            auth["auth"] = tuple(creds.split(":"))
                        case "azcopy":
                            out = subprocess.run(
                                ["azcopy", "copy", fp, creds],
                                capture_output=True,
                                check=False
                            )
                            if out.stderr:
                                logger.error(out.stderr)
                                raise PodWatcherException(
                                    "Something went wrong with the result push"
                                )
                            logger.info(out.stdout)
                            is_api = False
                        case _:
                            # This won't happen, as validation happend at CRD
                            # creation at k8s api level
                            pass
                    if is_api:
                        with open(fp, 'r', encoding="utf-8") as file:
                            resp = requests.post(
                                other_info.get("url"),
                                files={fp: file},
                                **auth
                            )
                        if not resp.ok:
                            raise PodWatcherException("Failed to deliver results")
                else:
                    raise PodWatcherException("No suitable delivery options available")
                # Add results annotation to let the controller know
                # we already handled results
                KubernetesCRD().patch_crd_annotations(crd_name, annotations)
                break
            case "Failed":
                raise KubernetesException(
                    "Pod in failed status. Refreshing annotation on CRD to trigger a restart"
                )
            case _:
                logger.info(
                    "%s Status: %s",
                    pod["object"].metadata.name,
                    pod["object"].status.phase
                )

    logger.info("Stopping task %s pod watcher", task_id)
    pod_watcher.stop()


def watch_user_pod(crd_name:str, user:str, labels:dict, annotations:dict):
    """
    Given a task id, checks for active pods with
    task_id label, and once completed, trigger the results fetching
    """
    pod_watcher = Watch()
    ls = ",".join(f"{lab[0]}={lab[1]}" for lab in labels.items())
    for job in pod_watcher.stream(
        KubernetesV1Batch().list_namespaced_job,
        NAMESPACE,
        label_selector=ls,
        resource_version='',
        watch=True
    ):
        logger.info("Found job! %s", job["object"].metadata.name)
        match get_job_status(job["object"].status):
            case "Succeeded":
                annotations[f"{DOMAIN}/user"] = "ok"
                # Add results annotation to let the controller know
                # we already handled the user
                KubernetesCRD().patch_crd_annotations(crd_name, annotations)
                break
            case "Failed":
                raise KubernetesException(
                    "Job in failed status. Refreshing annotation on CRD to trigger a restart"
                )
            case _:
                logger.info(
                    "%s Status: %s",
                    job["object"].metadata.name,
                    get_job_status( job["object"].status)
                )

    logger.info("Stopping %s job watcher", " ".join(user.values()))
    pod_watcher.stop()


def get_job_status(status:V1JobStatus) -> str:
    """
    Just a simple mapper as job status objects do not tell you directly
    what the status is, and spreads it across different vars
    """
    possible_status = ["Ready", "Terminating", "Active", "Succeeded", "Failed"]
    for state in possible_status:
        if getattr(status, state.lower(), False):
            return state
    # Mostly for aks clusters
    if getattr(getattr(status, "uncounted_terminated_pods"), "succeeded"):
        return "Succeeded"
    # Let's assume it's failed if the status is not on what we expect
    return "Failed"
