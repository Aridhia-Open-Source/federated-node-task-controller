#!/bin/bash
#
# Runs the controller image's azcopy against Azurite, the way the pod watcher delivers
# results: `azcopy copy <zip> <url-with-sas>`, as the non-root user from the deployment's
# securityContext, failing on any stderr output.
#
# Covers what the unit tests mock away: the azcopy build that is installed, and that it can
# run at all as a user with no home directory.
#
#   IMAGE=... TAG=... scripts/tests/integration/azcopy.sh

set -euo pipefail

IMAGE=${IMAGE:-ghcr.io/aridhia-open-source/fn_task_controller}
TAG=${TAG:-1.0}
AZURITE_IMAGE=mcr.microsoft.com/azure-storage/azurite:3.35.0
HELPER_IMAGE=python:3.13.5-slim
AZURE_BLOB_VERSION=12.30.3

HERE="$(cd "$(dirname "$0")" && pwd)"
RUN_ID="azcopy-it-$$"
NETWORK="$RUN_ID"
WORKDIR="$(mktemp -d)"

cleanup() {
  docker rm -f "$RUN_ID-azurite" > /dev/null 2>&1 || true
  docker network rm "$NETWORK" > /dev/null 2>&1 || true
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

helper() {
  docker run --rm --network "$NETWORK" \
    -v "$HERE/azurite_helper.py":/azurite_helper.py:ro \
    "$HELPER_IMAGE" sh -c \
    "pip install --quiet --disable-pip-version-check --root-user-action=ignore azure-storage-blob==$AZURE_BLOB_VERSION && python /azurite_helper.py $*"
}

echo "== azcopy is the pinned stable build"
expected=$(grep -oP '\bazcopy=\K[^ ]+' "$HERE/../../../Dockerfile")
installed=$(docker run --rm --entrypoint azcopy "$IMAGE:$TAG" --version | awk '{print $3}')
[[ "$installed" == "$expected" ]] || fail "azcopy is $installed, Dockerfile pins $expected"
[[ "$installed" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "azcopy $installed is a pre-release"
echo "azcopy $installed"

echo "== starting Azurite"
docker network create "$NETWORK" > /dev/null
docker run -d --name "$RUN_ID-azurite" --network "$NETWORK" \
  --network-alias devstoreaccount1.blob.azurite \
  "$AZURITE_IMAGE" azurite-blob --blobHost 0.0.0.0 --loose --skipApiVersionCheck > /dev/null
for _ in $(seq 30); do
  docker logs "$RUN_ID-azurite" 2>&1 | grep -q "successfully listens" && break
  sleep 1
done
sas_url=$(helper sas results | tail -1)
[[ "$sas_url" == http* ]] || fail "could not create a container on Azurite: $sas_url"

echo "== uploading as the controller's runtime user"
echo "results from $RUN_ID" > "$WORKDIR/results.zip"
chmod 644 "$WORKDIR/results.zip"
dest="${sas_url%%\?*}/results.zip?${sas_url#*\?}"
set +e
docker run --rm --network "$NETWORK" \
  --user 1001:1001 --cap-drop ALL --security-opt no-new-privileges \
  -v "$WORKDIR/results.zip":/data/results.zip:ro \
  "$IMAGE:$TAG" azcopy copy /data/results.zip "$dest" \
  > "$WORKDIR/stdout" 2> "$WORKDIR/stderr"
status=$?
set -e
if [[ $status -ne 0 || -s "$WORKDIR/stderr" ]]; then
  cat "$WORKDIR/stdout" "$WORKDIR/stderr" >&2
  fail "azcopy exited $status; the pod watcher treats any stderr as a failed delivery"
fi

echo "== checking the blob"
uploaded=$(helper read results results.zip 2> /dev/null | tail -1) \
  || fail "azcopy reported success but results.zip is not in the container"
[[ "$uploaded" == "results from $RUN_ID" ]] || fail "blob content was '$uploaded'"

echo "PASS"
