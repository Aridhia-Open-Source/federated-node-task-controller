#!/bin/sh

set -eu

# User-defined variables
PRE_LINT=${PRE_LINT:-"pip3 install --no-cache-dir pipenv && pipenv install --categories \"packages dev-packages\" && pipenv run "} # Bash to run before executing the linter
OUTPUT_DIR=${OUTPUT_DIR:-artifacts} # Path to write the results file in

# Internal variables
BUILD_ID=${BUILD_ID:-$(uuidgen)}
container_name="pylint_${BUILD_ID}"

set +e
docker build . -f test.Dockerfile -t federated_node_controller_lint

echo "Running linter"
echo
docker run \
  --workdir /app/controller \
  --init \
  -e PYTHONPATH=/app/controller \
  --name "${container_name}" \
  --entrypoint "/app/scripts/pylint-entrypoint.sh" \
  federated_node_controller_lint

exit_status=$?
set -e
docker cp "${container_name}":/tmp/pylint.xml "${OUTPUT_DIR}/pylint.xml"
docker rm "${container_name}"
exit "${exit_status}"

