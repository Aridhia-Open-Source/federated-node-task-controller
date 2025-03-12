#!/bin/sh

set -e

CURL_PARAMS="-k --location"

echo "Getting GitHub App token"
# shellcheck disable=SC1091
. "$(dirname "$0")/jwt.sh"

echo "Cloning repo"
gh repo clone "${GH_REPO}" "${REPO_FOLDER}"
cd "${REPO_FOLDER}" || exit
echo "Getting user info"
AUTHOR_USERNAME=$(gh pr list -B "${BRANCH}" --state merged --json author,mergedAt,mergedBy,headRefName,number | jq -r '.[0].author.login')
FULL_NAME=$(gh api -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" "/users/${AUTHOR_USERNAME}" | jq -r '.name')
USER_ID=$(gh api -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" "/users/${AUTHOR_USERNAME}" | jq -r '.id')
EMAILS=$(gh pr list -B "${BRANCH}" --state merged --json author,commits | jq -r "[.[] | .commits[] | .authors[] | select(.name == \"${FULL_NAME}\") | .email] | unique | .[]")

echo "Logging in Keycloak"
# shellcheck disable=SC2086
ADMIN_TOKEN=$(curl ${CURL_PARAMS} --fail-with-body "${KC_HOST}/realms/FederatedNode/protocol/openid-connect/token" \
    --header 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode 'grant_type=password' \
    --data-urlencode "username=${KC_USER}" \
    --data-urlencode "password=${KC_PASS}" \
    --data-urlencode 'client_id=admin-cli' | jq -r '.access_token')

for em in ${EMAILS}
do
    # shellcheck disable=SC2086
    KC_USER_ID=$(curl ${CURL_PARAMS} "${KC_HOST}/admin/realms/FederatedNode/users?email=${em}" \
        --header "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.[].id')

    if [ -n "${KC_USER_ID}" ]; then
        # shellcheck disable=SC2086
        curl ${CURL_PARAMS} "${KC_HOST}/admin/realms/FederatedNode/users/${KC_USER_ID}/federated-identity/$FULL_REPO" \
            --header 'Content-Type: application/json' \
            --header "Authorization: Bearer ${ADMIN_TOKEN}" \
            --data "{
                \"userId\": \"${USER_ID}\",
                \"userName\": \"${AUTHOR_USERNAME}\"
            }"
        echo
        echo "IdP link created or already exists"
        exit 0
    else
        echo "No users found with email ${em}"
    fi
done
rm -r "${REPO_FOLDER}"
exit 1
