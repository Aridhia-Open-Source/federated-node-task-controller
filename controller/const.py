"""
Centralized collection of constants and
environment variables
"""

import os

DOMAIN = "tasks.federatednode.com"
TASK_NAMESPACE = os.getenv("TASK_NAMESPACE")
NAMESPACE = os.getenv("NAMESPACE", "controller")
PUBLIC_URL = os.getenv("PUBLIC_URL")
BACKEND_HOST = os.getenv("BACKEND_HOST")
GIT_HOME = os.getenv("GIT_HOME")
MOUNT_PATH = os.getenv("MOUNT_PATH")
PULL_POLICY = os.getenv("PULL_POLICY")
LOCAL_DEV = os.getenv("DEVELOPMENT")
KC_HOST = os.getenv("KC_HOST")
KC_USER = os.getenv("KC_USER")
IMAGE = os.getenv("IMAGE")
TAG = os.getenv("TAG")
MAX_RETRIES = 5
