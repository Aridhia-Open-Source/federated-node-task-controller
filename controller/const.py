import os

DOMAIN = "tasks.federatednode.com"
TASK_NAMESPACE = os.getenv("TASK_NAMESPACE")
NAMESPACE = os.getenv("NAMESPACE", "controller")
BACKEND_HOST = os.getenv("BACKEND_HOST")
GIT_HOME = os.getenv("GIT_HOME")
MOUNT_PATH = os.getenv("MOUNT_PATH")
PULL_POLICY = os.getenv("PULL_POLICY")
LOCAL_DEV = os.getenv("DEVELOPMENT")
KC_URL = os.getenv("KC_URL")
KC_USER = os.getenv("KC_USER")
TAG = os.getenv("TAG")
