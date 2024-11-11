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
export REPO_FOLDER=/results
export KC_USER=admin
export KC_PASS=password1
export KEYCLOAK_ADMIN_PASSWORD=password1
export BRANCH=pipe-test
export KEY_FILE=scripts/tes-results.2024-10-03.private-key.pem
export GH_CLIENT_ID=asdasdasd
export GITHUB_CLIENTID=asdasdasd
export IMAGE=ghcr.io/aridhia-open-source/fn_task_controller
export TAG=0.0.1
export RUN_PYTESTS=1

pytest -v --cov-report xml:artifacts/coverage.xml --cov=controller .
pycobertura show artifacts/coverage.xml
