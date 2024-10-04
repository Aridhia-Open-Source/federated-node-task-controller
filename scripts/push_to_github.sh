#!/bin/sh
GH_CLIENT_ID=$1
KEY_FILE=$2

export GH_CLIENT_ID KEY_FILE
REPO_FOLDER=results

if [ -z "$TASK_ID" ]; then
    echo "TASK ID not provided"
    exit 1
fi

. ./jwt.sh

echo "Setting up GitHub"
git config --global user.email "fn@phems.com"
git config --global user.name "FNController"

if [ -d "repo " ]; then
    rm -r repo
fi
echo "Cloning repo"
gh repo clone "${GH_ORGANIZATION}/${GH_REPO}" "${REPO_FOLDER}"
(
    cd "${REPO_FOLDER}" || exit
    git remote remove origin
    git remote add origin https://"$APP_ID:$GH_TOKEN"@github.com/Aridhia-Open-Source/Federated-Node-Example-App.git
    git fetch
    BRANCH="${TASK_ID}-results"

    echo "Pulling or creating the results branch"
    if git checkout "${BRANCH}"; then
        git branch --set-upstream-to=origin/"${BRANCH}" "${BRANCH}"
        git pull
    else
        git checkout -b "${BRANCH}"
    fi


    openssl rand -base64 15 > test.txt
    mv ../*.tar "${TASK_ID}"/

    git add .
    git commit -am "${TASK_ID} Results"

    git push --set-upstream origin "${BRANCH}" || git push
    echo "Changes pushed"
)

rm -rf "${REPO_FOLDER}"
