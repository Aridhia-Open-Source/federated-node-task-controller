import logging
import asyncio

from const import NAMESPACE
from exceptions import CRDException
from helpers.kubernetes_helper import (
    KubernetesCRD, KubernetesV1Batch,
    KubernetesV1
)
from helpers.pod_watcher import watch_task_pod, watch_user_pod
from helpers.task_helper import create_fn_task, get_user_token
from models.crd import Analytics


logging.basicConfig()
logger = logging.getLogger('actions')
logger.setLevel(logging.INFO)


async def sync_users(crds: Analytics, annotations:dict):
    """
    Ensures that the user is already in keycloak and associated
    with the gihub IdP
    """
    # should trigger the user check
    KubernetesV1Batch().create_helper_job(
        f"link-user",
        create_volumes=False,
        script="sync_user.sh",
        labels=crds.labels,
        repository=crds.source["repository"],
        user=crds.user
    )

    await watch_user_pod(crds, annotations)

async def trigger_task(crd: Analytics, annotations):
    """
    Common function to setup all the info necessary
    to send a FN API request, and the POST /tasks itself
    """
    user_token = await get_user_token(crd.user)
    logger.info("Creating task with image %s", crd.image)

    task_resp = create_fn_task(crd, user_token)

    annotations[f"{crd.domain}/done"] = "true"
    if "task_id" in task_resp:
        annotations[f"{crd.domain}/task_id"] = str(task_resp["task_id"])
    client = KubernetesCRD()
    client.patch_crd_annotations(crd.name, annotations)

async def handle_results(crd: Analytics, annotations:dict):
    """
    Common function to handle a CRD last lifecycle step
    """
    # If we have already triggered a task, check if the pod has completed
    # loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    monitor = asyncio.create_task(
        watch_task_pod(
            crd,
            annotations[f"{Analytics.domain}/task_id"],
            await get_user_token(crd.user),
            annotations
        )
    )
    await asyncio.gather(monitor)

async def create_retry_job(crd:Analytics):
    """
    Wrapper to create a job that updates the CRD
    with an increasing delay. It will retry up to
    MAX_RETRIES times.
    """
    try:
        existing_updates = KubernetesV1().list_namespaced_pod(
            NAMESPACE,
            label_selector=f"crd={crd.name}",
            field_selector="status.phase=Pending,status.phase=Running"
        )
        if existing_updates.items:
            logging.info("Anoter annotation update is in progress..")
            return

        KubernetesV1Batch().create_bare_job(**crd.prepare_update_job())
    except CRDException:
        pass
