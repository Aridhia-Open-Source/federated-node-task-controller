"""
Kubernetes controller to handle the Custom Resource Definition Analytics
The goal is simple, all new CRDs should trigger a new task on the FN.
"""
from copy import deepcopy
import logging
import traceback
import urllib3
from kubernetes.watch import Watch
from kubernetes.client.exceptions import ApiException

from const import DOMAIN, TASK_NAMESPACE
from excpetions import FederatedNodeException, KeycloakException
from helpers.kubernetes_helper import v1_custom_objects, k8s_config
from helpers.actions import sync_users, trigger_task, handle_results, create_retry_job
logging.basicConfig()
logger = logging.getLogger('controller')
logger.setLevel(logging.INFO)

k8s_config()


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

            new_annotations = deepcopy(annotations)

            if crds["type"] == "ADDED" and not annotations.get(f"{DOMAIN}/user"):
                sync_users(crds, new_annotations, user)
            elif annotations.get(f"{DOMAIN}/user") and not annotations.get(f"{DOMAIN}/done"):
                trigger_task(user, image, crd_name, proj_name, dataset, new_annotations)
            elif annotations.get(f"{DOMAIN}/done") and not annotations.get(f"{DOMAIN}/results"):
                handle_results(user, crds, crd_name, new_annotations)
            if exit_on_tests:
                watcher.stop()
                break
        except urllib3.exceptions.MaxRetryError as mre:
            # in case of unreachable URLs we want to fail and exit
            logger.error(mre.reason)
            raise mre
        except (KeycloakException, FederatedNodeException, ApiException) as ke:
            create_retry_job(crd_name, annotations)
            logger.error(ke.reason)
        except KeyError:
            # Possibly missing values, it shouldn't crash the pod
            logger.error(traceback.format_exc())
        # pylint: disable=W0718
        except Exception:
            create_retry_job(crd_name, annotations)
            logger.error("Unknown error: %s", traceback.format_exc())
