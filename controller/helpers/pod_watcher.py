import base64
import logging
import requests
import subprocess
from kubernetes.watch import Watch
from kubernetes.client.models.v1_job_status import V1JobStatus

from const import DOMAIN, TASK_NAMESPACE, NAMESPACE
from excpetions import KubernetesException, BaseControllerException
from helpers.kubernetes_helper import KubernetesV1Batch, KubernetesCRD, KubernetesV1
from helpers.task_helper import get_results

logging.basicConfig()
logger = logging.getLogger('pod_watcher')
logger.setLevel(logging.INFO)


def watch_task_pod(crd_name:str, crd_spec:dict, task_id:str, user_token:str, annotations:dict):
    """
    Given a task id, checks for active pods with
    task_id label, and once completed, trigger the results fetching
    """
    git_info = crd_spec["results"].get("git")
    other_info = crd_spec["results"].get("other")
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
                    else:
                        auth = {}
                        is_api = True
                        # other_info["auth"] might be moved somewhere else
                        # but for now is passed as CRD field
                        creds = other_info.get("auth", '')
                        match other_info.get("auth_type", '').lower():
                            case "bearer":
                                auth["headers"] = {"Authorization": f"Bearer {creds}"}
                            case "basic":
                                auth["auth"] = tuple(base64.b64decode(creds).split(":"))
                            case "azcopy":
                                out = subprocess.run(
                                    ["azcopy", "copy", fp, creds],
                                    capture_output=True
                                )
                                if out.stderr:
                                    logger.error(out.stderr)
                                    raise BaseControllerException("Something went wrong with the result push")
                                logger.info(out.stdout)
                                is_api = False
                            case _:
                                pass
                        if is_api:
                            resp = requests.post(other_info.get("url"),**auth)
                            if not resp.ok:
                                raise BaseControllerException("Failed to deliver results")

                    # Add results annotation to let the controller know
                    # we already handled results
                    KubernetesCRD().patch_crd_annotations(crd_name, annotations)
                    break
                case "Failed":
                    raise KubernetesException("pod in failed status. Refreshing annotation on CRD to trigger a restart")
                case _:
                    logger.info("%s Status: %s",  pod["object"].metadata.name, pod["object"].status.phase)

    logger.info(f"Stopping task {task_id} pod watcher")
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
                    raise KubernetesException("Job in failed status. Refreshing annotation on CRD to trigger a restart")
                case _:
                    logger.info("%s Status: %s", job["object"].metadata.name, get_job_status( job["object"].status))

    logger.info(f"Stopping {" ".join(user.values())} job watcher")
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
