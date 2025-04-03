import json
from math import exp
import re

from excpetions import CRDException

MAX_RETRIES = 5


class Analytics:
    domain = "tasks.federatednode.com"

    def __init__(
            self,
            crd_definition:dict
        ):
        self.name = crd_definition["object"]["metadata"]["name"]
        self.annotations = crd_definition["object"]["metadata"]["annotations"]
        self.image = crd_definition["object"]["spec"].get("image", {})
        if not self.image:
            raise CRDException("image field is required")

        self.user = crd_definition["object"]["spec"].get("user", {})
        if not self.user:
            raise CRDException("user field is required")

        self.proj_name = crd_definition["object"]["spec"].get("project")
        if not self.proj_name:
            raise CRDException("project field is required")

        self.dataset = crd_definition["object"]["spec"].get("dataset", {})
        self.env = crd_definition["object"]["spec"].get("env", {})
        self.outputs = crd_definition["object"]["spec"].get("outputs", {})
        self.inputs = crd_definition["object"]["spec"].get("inputs", {})
        self.source = crd_definition["object"]["spec"].get("source", {})
        self.delivery = json.load(open("controller/delivery.json"))
        self.create_labels()
        self.is_delete = (crd_definition["type"] == "DELETED" or crd_definition["object"]["metadata"].get("deletionTimestamp"))

    def needs_user_sync(self) -> bool:
        return not self.annotations.get(f"{self.domain}/user")

    def can_trigger_task(self) -> bool:
        return self.annotations.get(f"{self.domain}/user") and not self.annotations.get(f"{self.domain}/done")

    def can_deliver_results(self) -> bool:
        return self.annotations.get(f"{self.domain}/done") and not self.annotations.get(f"{self.domain}/results")

    def should_skip(self) -> bool:
        return bool(self.is_delete or self.annotations.get(f"{self.domain}/results"))

    def create_labels(self):
        """
        Given the crd spec dictionary, creates a dictionary
        to be used as a labels set. Trims each field to
        64 chars as that's k8s limit
        """
        self.labels = {}
        if self.dataset:
            self.labels["dataset"] = "-".join(self.dataset.values())[:63]

        self.labels["user"] = "".join(self.user.values())
        self.labels["repository"] = self.source["repository"].replace("/", "-")[:63]
        if self.delivery.get("github"):
            self.labels["repository_results"] = self.delivery["github"]["repository"].replace("/", "-")[:63]
        else:
            self.labels["results"] = self.delivery["other"].get("url") or self.delivery["other"]["auth_type"]
        self.labels["image"] = re.sub(r'(\/|:)', '-', self.image)[:63]

    def create_task_body(self) -> dict:
        """
        The task body is fairly strict, so we are going to inject few
        custom data in it, like a docker image, a user, a project name and the dataset
        to run the task on
        """
        return {
            "name": self.user.get("username") or self.user.get("email"),
            "executors": [
                {
                    "image": self.image,
                    "env": self.env
                }
            ],
            "dataset_id": self.dataset.get("id"),
            "dataset_name": self.dataset.get("name"),
            "tags": {
                "dataset_id": self.dataset.get("id"),
                "dataset_name": self.dataset.get("name")
            },
            "inputs": self.inputs,
            "outputs": self.outputs,
            "volumes": {},
            "description": f"Automated task for {self.proj_name} project",
            "task_controller": True
        }

    def prepare_update_job(self) -> dict:
        """
        Wrapper to create a job that updates the CRD
        with an increasing delay. It will retry up to
        MAX_RETRIES times.
        """
        annotation_check = "tasks.federatednode.com/tries"
        current_try = int(self.annotations.get(annotation_check, 0)) + 1

        if current_try > MAX_RETRIES:
            raise CRDException("Max retries reached. Skipping")
        cooldown = int(exp(current_try))

        cmd = f"sleep {cooldown} && " \
            f"kubectl get analytics {self.name} -o json |"\
            f" jq '.metadata.annotations += {{\"{annotation_check}\": \"{current_try}\"}}' | "\
            "kubectl replace -f-"

        return {
            "name": f"update-annotation-{self.name}",
            "command": cmd,
            "run": True,
            "labels": {
                "cooldown": f"{cooldown}s",
                "crd": self.name
            },
            "image": "alpine/k8s:1.29.4"
        }
