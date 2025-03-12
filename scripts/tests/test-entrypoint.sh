#!/bin/sh

set -e

echo "Setting env vars"
export TASK_NAMESPACE=analytics
export NAMESPACE=fn-controller-test
export BACKEND_HOST=http://localhost:5000
export KC_HOST=http://localhost:8081
export GIT_HOME=/data/controller
export FLASK_DEBUG=1
export GH_REPO=Aridhia-Open-Source/Federated-Node-Example-App
export REPO_FOLDER=/controller
export KC_USER=admin
export KC_PASS=password1
export KEYCLOAK_ADMIN_PASSWORD=password1
export IMAGE=ghcr.io/aridhia-open-source/fn_task_controller
export TAG=0.0.1
export MOUNT_PATH=/data/test

pytest -v --cov-report xml:/app/artifacts/coverage.xml --cov=controller .
pycobertura show /app/artifacts/coverage.xml
