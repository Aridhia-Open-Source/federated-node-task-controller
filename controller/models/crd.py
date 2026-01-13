import json
from math import exp
import os
import re

from const import CRD_GROUP
from exceptions import CRDException

MAX_RETRIES = 5


class Analytics:
    domain = CRD_GROUP

    def __init__(
            self,
            crd_definition:dict
        ):
        self.name = crd_definition["object"]["metadata"]["name"]
        self.status = crd_definition["object"].get("status", {})
        self.image = crd_definition["object"]["spec"].get("image", {})
        self.dict = crd_definition["object"]
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
        self.query = crd_definition["object"]["spec"].get("db_query")
        self.delivery = json.load(open("controller/delivery.json"))
        self.create_labels()
        self.is_delete = (crd_definition["type"] == "DELETED" or crd_definition["object"]["metadata"].get("deletionTimestamp"))

    def needs_user_sync(self) -> bool:
        return not self.status.get("userMigrated")

    def can_trigger_task(self) -> bool:
        return self.status.get("userMigrated") and not self.status.get("taskID")

    def can_deliver_results(self) -> bool:
        """
        Overcomplicated flow control, but there are few requirements to
        fetch results:
        - done HAS to be there, which means task pod is done
        - results HAS NOT to be there, meaning results have not been fetched and delivered yet

        TASK_REVIEW and approved annotation should make the whole check fail when:
            TASK_REVIEW is set and approved is not "true". So we check for this
            case, and negate it.
        """
        return self.status.get("taskID") and \
            not self.status.get("resultsDelivered") and \
            not (
                os.getenv("TASK_REVIEW") is not None and \
                not self.status.get("approved", False)
            )

    def should_skip(self) -> bool:
        return bool(self.is_delete or self.status.get("resultsDelivered"))

    def to_dict(self) -> dict:
        self.dict.update(self.status)
        return self.dict

    def create_labels(self):
        """
        Given the crd spec dictionary, creates a dictionary
        to be used as a labels set. Trims each field to
        64 chars as that's k8s limit
        """
        self.labels = {}
        if self.dataset:
            self.labels["dataset"] = "-".join(self.dataset.values())[:63]

        self.labels.update(self.user)
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
        base = {
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
        if self.query:
            base["db_query"] = self.query

        return base

    def prepare_update_job(self) -> dict:
        """
        Wrapper to create a job that updates the CRD
        with an increasing delay. It will retry up to
        MAX_RETRIES times.
        """
        current_try = int(self.status.get("retries", 0)) + 1

        if current_try > MAX_RETRIES:
            raise CRDException("Max retries reached. Skipping")
        cooldown = int(exp(current_try))

        cmd = f"sleep {cooldown} && " \
            f"kubectl patch analytics {self.name} --type=merge --subresource=status -p '{{\"status\": {{\"retries\": {current_try}}}}}'"

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
