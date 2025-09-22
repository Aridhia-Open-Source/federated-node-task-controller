#!/bin/sh

set -e

if [[ -z "$PR_NUM" ]]; then
    echo "Missing PR number. Exiting"
    exit 1
fi
if [[ -z "$FN_HOST" ]]; then
    echo "Missing FN host. Exiting"
    exit 1
fi

echo "Getting GitHub App token"
# shellcheck disable=SC1091
. "$(dirname "$0")/jwt.sh"

echo """
@${USER_NAME} Erorr reported on Task from ${FN_HOST}
\`\`\`
${ERROR_LOGS:-"No logs available, ask the maintainer"}
\`\`\`
""" | gh pr comment "${PR_NUM}" -F -
