"""
Collection of job and pod watchers.
    - Pod watcher monitors the actual task lifecycle
    - Job watcher is mostly to focus on user sync
"""

import asyncio
import base64
import logging
import re
import subprocess
import httpx
from kubernetes.watch import Watch
from kubernetes.client.models.v1_job_status import V1JobStatus

from const import TASK_NAMESPACE, NAMESPACE
from exceptions import KubernetesException, PodWatcherException
from helpers.kubernetes_helper import KubernetesV1Batch, KubernetesCRD, KubernetesV1
from helpers.request_helper import client as requests
from helpers.task_helper import get_results
from models.crd import Analytics

logging.basicConfig()
logger = logging.getLogger('pod_watcher')
logger.setLevel(logging.INFO)

MAX_TIMEOUT = 60


async def watch_task_pod(crd: Analytics, task_id:str, user_token:str, annotations:dict):
    """
    Given a task id, checks for active pods with
    task_id label, and once completed, trigger the results fetching
    """
    pod = None
    git_info = crd.delivery.get("github", {})
    other_info = crd.delivery.get("other", {})
    logger.info("Looking for pod with task_id: %s", task_id)
    pod_watch = Watch()

    for pod in pod_watch.stream(
        KubernetesV1().list_namespaced_pod,
        TASK_NAMESPACE,
        label_selector=f"task_id={task_id}",
        timeout_seconds=MAX_TIMEOUT
    ):
        logger.info("Found pod! %s", pod["object"].metadata.name)
        match pod["object"].status.phase:
            case "Succeeded":
                annotations[f"{crd.domain}/results"] = "true"
                fp = await get_results(task_id, user_token)
                if fp is None:
                    logging.info("Task needs a review")
                    # Results to be approved. Waiting. No retries
                    break
                if git_info:
                    KubernetesV1Batch().create_helper_job(
                        name=f"task-{task_id}-results",
                        script="push_to_github.sh",
                        task_id=task_id,
                        repository=git_info.get("repository"),
                        crd_name=crd.name,
                        user=crd.user
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
                            resp = httpx.post(
                                other_info.get("url"),
                                files={fp: file},
                                **auth
                            )
                        if resp.status_code > 299:
                            raise PodWatcherException("Failed to deliver results")
                    # Add results annotation to let the controller know
                    # we already handled results
                    KubernetesCRD().patch_crd_annotations(crd.name, annotations)
                else:
                    raise PodWatcherException("No suitable delivery options available")
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
    if not pod:
        raise KubernetesException(f"Timeout. Pod for task {task_id} not found")
    pod_watch.stop()


async def watch_user_pod(crd: Analytics, annotations:dict):
    """
    Given a task id, checks for active pods with
    task_id label, and once completed, trigger the results fetching
    """
    pod_watch = Watch()
    ls = ",".join(f"{lab[0]}={lab[1]}" for lab in crd.labels.items())
    for job in pod_watch.stream(
        KubernetesV1Batch().list_namespaced_job,
        NAMESPACE,
        label_selector=ls,
        resource_version='',
        watch=True,
        timeout_seconds=MAX_TIMEOUT
    ):
        logger.info("Found job! %s", job["object"].metadata.name)
        match await get_job_status(job["object"].status):
            case "Succeeded":
                annotations[f"{crd.domain}/user"] = "ok"
                # Add results annotation to let the controller know
                # we already handled the user
                KubernetesCRD().patch_crd_annotations(crd.name, annotations)
                break
            case "Failed":
                raise KubernetesException(
                    "Job in failed status. Refreshing annotation on CRD to trigger a restart"
                )
            case _:
                logger.info(
                    "%s Status: %s",
                    job["object"].metadata.name,
                    await get_job_status(job["object"].status)
                )

    logger.info("Stopping %s job watcher", " ".join(crd.user.values()))
    pod_watch.stop()


async def get_job_status(status:V1JobStatus) -> str:
    """
    Just a simple mapper as job status objects do not tell you directly
    what the status is, and spreads it across different vars
    """
    possible_status = ["Ready", "Terminating", "Active", "Succeeded", "Failed"]
    for state in possible_status:
        if getattr(status, state.lower(), False):
            return state
    # Mostly for aks clusters
    if getattr(getattr(status, "uncounted_terminated_pods", V1JobStatus), "succeeded", []):
        return "Succeeded"
    # Let's assume it's failed if the status is not on what we expect
    return "Failed"
