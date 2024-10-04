import os

DOMAIN = "tasks.federatednode.com"
TASK_NAMESPACE = os.getenv("TASK_NAMESPACE")
NAMESPACE = os.getenv("NAMESPACE", "controller")
BACKEND_HOST = os.getenv("BACKEND_HOST")
GIT_HOME = os.getenv("GIT_HOME")
