from copy import deepcopy
import logging
import re
from math import exp

from const import DOMAIN, MAX_RETRIES
from helpers.kubernetes_helper import (
    KubernetesCRD, KubernetesV1Batch
)
from helpers.pod_watcher import watch_task_pod, watch_user_pod
from helpers.task_helper import create_task, get_user_token

logging.basicConfig()
logger = logging.getLogger('actions')
logger.setLevel(logging.INFO)


def create_labels(crds:dict) -> dict:
    """
    Given the crd spec dictionary, creates a dictionary
    to be used as a labels set. Trims each field to
    64 chars as that's k8s limit
    """
    labels = deepcopy(crds)
    labels["dataset"] = "-".join(labels["dataset"].values())[:63]
    labels.update(labels.pop("user"))
    labels["repository"] = labels["source"]["repository"].replace("/", "-")[:63]
    labels.pop("source")
    if labels["results"].get("git"):
        labels["repository_results"] = labels["results"]["git"]["repository"].replace("/", "-")[:63]
    else:
        other = labels["results"]["other"]
        labels["results"] = other.get("url") or other["auth_type"]
    labels["image"] = re.sub(r'(\/|:)', '-', labels["image"])[:63]
    return labels


def sync_users(crds: dict, annotations:dict, user:dict):
    """
    Ensures that the user is already in keycloak and associated
    with the gihub IdP
    """
    labels = create_labels(crds["object"]["spec"])

    # should trigger the user check
    KubernetesV1Batch().create_helper_job(
        f"link-user-{"".join(user.values())}",
        script="init_container.sh",
        create_volumes=False,
        labels=labels,
        repository=crds["object"]["spec"]["source"].get("repository")
    )

    watch_user_pod(crds["object"]["metadata"]["name"], user, labels, annotations)

def trigger_task(user:str, image:str, crd_name:str, proj_name:str, dataset:str, annotations:dict):
    """
    Common function to setup all the info necessary
    to send a FN API request, and the POST /tasks itself
    """
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
    client = KubernetesCRD()
    client.patch_crd_annotations(crd_name, annotations)

def handle_results(user:str, crds:dict, crd_name:str, annotations:dict):
    """
    Common function to handle a CRD last lifecycle step
    """
    # If we have already triggered a task, check if the pod has completed
    watch_task_pod(
        crd_name,
        crds["object"]["spec"],
        annotations[f"{DOMAIN}/task_id"],
        get_user_token(user),
        annotations
    )

def create_retry_job(crd_name:str, annotations:dict):
    """
    Wrapper to create a job that updates the CRD
    with an increasing delay. It will retry up to
    MAX_RETRIES times.
    """
    annotation_check = "tasks.federatednode.com/tries"
    current_try = int(annotations.get(annotation_check, 0)) + 1

    if current_try > MAX_RETRIES:
        return
    cooldown = int(exp(current_try))

    cmd = f"sleep {cooldown} && " \
        f"kubectl get analytics -n analytics {crd_name} -o json |"\
        f" jq '.metadata.annotations += {{\"{annotation_check}\": \"{current_try}\"}}' | "\
        "kubectl replace -f-"

    KubernetesV1Batch().create_bare_job(
        f"update-annotation-{crd_name}",
        command=cmd,
        run=True,
        labels={
            "cooldown": f"{cooldown}s",
            "crd": crd_name
        },
        image="alpine/k8s:1.29.4"
    )
