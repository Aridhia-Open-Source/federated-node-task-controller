"""
Kubernetes controller to handle the Custom Resource Definition Analytics
The goal is simple, all new CRDs should trigger a new task on the FN.

The lifecycle is documented through labels:
    - user: ok          -> the external identity on github is confirmed and linked
    - task_id: <int>    -> task triggered, waiting for completion
    - results: true     -> results fetched
    - done: true        -> All done, results pushed successfully
    - tries: <1:5>      -> There is a max of 5 retries with exponential waiting times
"""
from copy import deepcopy
import logging
import traceback
from urllib3.exceptions import MaxRetryError, ProtocolError
from kubernetes.watch import Watch
from kubernetes.client.exceptions import ApiException

from excpetions import BaseControllerException
from helpers.kubernetes_helper import KubernetesCRD
from helpers.actions import create_retry_job, sync_users, trigger_task, handle_results
from models.crd import Analytics


logging.basicConfig()
logger = logging.getLogger('controller')
logger.setLevel(logging.INFO)


def start(exit_on_tests=False):
    """
    Effectively the entrypoint of the controller.
    Accepts the `exit_on_tests` argument which is mostly,
    as the name suggests, used for tests and has to be explicitly
    set via a code change rather than an env var
    """
    try:
        watcher = Watch()
        for crds in watcher.stream(
            KubernetesCRD().list_cluster_custom_object,
            Analytics.domain,
            "v1",
            "analytics"
            ):
            crd = Analytics(crds)
            try:
                logger.info("CRD: %s", crd.name)

                if crd.should_skip():
                    logger.info("CRD already processed")
                    continue

                new_annotations = deepcopy(crd.annotations)
                logger.info("Annotations: %s", new_annotations)
                if crd.needs_user_sync():
                    logger.info("Synching user")
                    sync_users(crd, new_annotations)
                elif crd.can_trigger_task():
                    logger.info("Triggering task")
                    trigger_task(crd, new_annotations)
                elif crd.can_deliver_results():
                    logger.info("Getting task results")
                    handle_results(crd, new_annotations)
                if exit_on_tests:
                    watcher.stop()
                    break
            except MaxRetryError as mre:
                # in case of unreachable URLs we want to fail and exit
                logger.error(mre.reason)
                raise mre
            except (BaseControllerException, ApiException) as ke:
                create_retry_job(crd)
                logger.error(ke.reason)
            except KeyError:
                # Possibly missing values, it shouldn't crash the pod
                logger.error(traceback.format_exc())
            # pylint: disable=W0718
            except Exception:
                create_retry_job(crd)
                logger.error("Unknown error: %s", traceback.format_exc())
    except ProtocolError as pe:
        logger.error("Connection expired. Restarting..")
        logger.info(pe.with_traceback())
