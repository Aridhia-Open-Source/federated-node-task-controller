#!/bin/sh

set -e

ARTIFACTS_DIR=artifacts

if [ ! -x "$(which xmlstarlet)" ]; then
  echo xmlstarlet not found, installing...
  sudo apt update
  sudo apt install xmlstarlet --no-install-recommends -y
fi

set +e

HADOLINT_IMAGE="hadolint/hadolint:v2.15.1-alpine"

#shellcheck disable=2046
result=$(docker run \
  --volume "$(pwd)":/mnt:ro \
  --workdir /mnt \
  --init \
  --rm \
  "$HADOLINT_IMAGE" hadolint -f checkstyle $(find . -type f -name "*Dockerfile"))
exit_status=$?
set -e
echo "$result" \
  | xmlstarlet tr scripts/tests/checkstyle2junit.xslt \
  > "$ARTIFACTS_DIR"/hadolint.xml
exit "$exit_status"
