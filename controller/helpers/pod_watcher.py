import logging
from kubernetes.watch import Watch

from const import TASK_NAMESPACE, NAMESPACE
from helpers.kubernetes_helper import v1, k8s_config, patch_crd_annotations, create_helper_job
from helpers.task_helper import get_results

logging.basicConfig()
logger = logging.getLogger('pod_watcher')
logger.setLevel(logging.INFO)

k8s_config()


def watch_task_pod(crd_name:str, crd_spec:dict, task_id:str, user_token:str, annotations:dict):
    """
    Given a task id, checks for active pods with
    task_id label, and once completed, trigger the results fetching
    """
    repository = crd_spec.get("repository")
    pod_watcher = Watch()
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
                create_helper_job(
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
    pod_watcher = Watch()
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
