import logging
import random
from kubernetes.watch import Watch

from const import DOMAIN, TASK_NAMESPACE, NAMESPACE
from helpers.kubernetes_helper import KubernetesV1, KubernetesV1Batch, KubernetesCRD
from helpers.task_helper import get_results

logging.basicConfig()
logger = logging.getLogger('pod_watcher')
logger.setLevel(logging.INFO)


def watch_task_pod(crd_name:str, crd_spec:dict, task_id:str, user_token:str, annotations:dict):
    """
    Given a task id, checks for active pods with
    task_id label, and once completed, trigger the results fetching
    """
    repository = crd_spec.get("repository")
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
                    get_results(task_id, user_token)
                    KubernetesV1Batch().create_helper_job(
                        name=f"task-{task_id}-results",
                        task_id=task_id,
                        repository=repository
                    )
                    # Add results annotation to let the controller know
                    # we already handled results
                    KubernetesCRD().patch_crd_annotations(crd_name, annotations)
                    break
                case "Failed":
                        logger.info("Pod in failed status. Refreshing annotation on CRD to trigger a restart")
                        annotations[f"{DOMAIN}/retry_hash"] = str(random.random() * 100)
                        KubernetesCRD().patch_crd_annotations(crd_name, annotations)
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
    for pod in pod_watcher.stream(
        KubernetesV1().list_namespaced_pod,
        NAMESPACE,
        label_selector=ls,
        resource_version='',
        watch=True
        ):
            logger.info("Found pod! %s", pod["object"].metadata.name)
            match pod["object"].status.phase:
                case "Succeeded":
                    annotations[f"{DOMAIN}/user"] = "ok"
                    # Add results annotation to let the controller know
                    # we already handled the user
                    KubernetesCRD().patch_crd_annotations(crd_name, annotations)
                    break
                case "Failed":
                    logger.info("Pod in failed status. Refreshing annotation on CRD to trigger a restart")
                    annotations[f"{DOMAIN}/retry_hash"] = str(random.random() * 100)
                    KubernetesCRD().patch_crd_annotations(crd_name, annotations)
                    break
                case _:
                    logger.info("%s Status: %s",  pod["object"].metadata.name, pod["object"].status.phase)

    logger.info(f"Stopping {" ".join(user.values())} pod watcher")
    pod_watcher.stop()
