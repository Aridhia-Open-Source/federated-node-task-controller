#!/usr/bin/env sh



pem=$( cat "$KEY_FILE" ) # file path of the private key as second argument

now=$(date +%s)
iat=$(( now - 60)) # Issues 60 seconds in the past
exp=$(( now + 600)) # Expires 10 minutes in the future

b64enc() { openssl base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n'; }

header_json='{
    "typ":"JWT",
    "alg":"RS256"
}'
# Header encode
header=$( echo "${header_json}" | b64enc )

payload_json="{
    \"iat\":${iat},
    \"exp\":${exp},
    \"iss\":\"${GH_CLIENT_ID}\"
}"
# Payload encode
payload=$( echo "${payload_json}" | b64enc )

# Signature
header_payload="${header}"."${payload}"
header_file=$(mktemp)
sig_file=$(mktemp)
printf '%s' "${header_payload}" > "${header_file}"
printf '%s' "${pem}" > "${sig_file}"

signature=$(
    openssl dgst -sha256 -sign "${sig_file}" "${header_file}" | b64enc
)

# Create JWT
JWT="${header_payload}"."${signature}"

RESP=$(curl --request GET \
    --url "https://api.github.com/app/installations" \
    --header "Accept: application/vnd.github+json" \
    --header "Authorization: Bearer ${JWT}" \
    --header "X-GitHub-Api-Version: 2022-11-28" | jq)
APP_ID=$(echo "$RESP" | jq -r '.[0].app_id')
INST_ID=$(echo "$RESP" | jq -r '.[0].id')
echo "AppID: $APP_ID"
echo "INST_ID: $INST_ID"
URL="https://api.github.com/app/installations/$INST_ID/access_tokens"
GH_TOKEN=$(curl --request POST \
    --url "$URL" \
    --header "Accept: application/vnd.github+json" \
    --header "Authorization: Bearer ${JWT}" \
    --header "X-GitHub-Api-Version: 2022-11-28" | jq -r '.token')
export GH_TOKEN
