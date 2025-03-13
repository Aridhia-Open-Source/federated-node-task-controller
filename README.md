[![Build Docker Image](https://github.com/Aridhia-Open-Source/federated-node-task-controller/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/Aridhia-Open-Source/federated-node-task-controller/actions/workflows/build.yml)
# Federated Node Task Controller (FNTC)

For the time being is on a separate repo, it might get merged in the main Federated Node one: [PHEMS_federated_node](https://github.com/Aridhia-Open-Source/PHEMS_federated_node)


This python controller aims to monitor a CRD which is defined in [this manifest](./k8s/fn-task-controller/templates/crd.yaml) and translate it into an internal request to the federated node to `POST /tasks`.

After creating a task successfully, it will periodically check for the status and push the results, once the task pod completes, on a github repository.

### How does this work?
Let's imagine that the source code to run some analytics is hosted in github in repo `average_analysis`.

In this repo there will be a folder where the CRD defined [here](./k8s/fn-task-controller/templates/crd.yaml) is hosted as template.

ArgoCD will start monitoring this repo on a dedicated branch, set to read-only for all users, except the Admins.

There will also be a pipeline (i.e [example](https://github.com/Aridhia-Open-Source/Federated-Node-Example-App/blob/pipe-test/.github/workflows/triggertask.yml)) that refers to another actions template (provided by us), which takes care of (upon merge to a user-defined branch) merging the CRD changes to a third branch (i.e. `monitor`) which ArgoCD is monitoring for changes. It also injects the username on the PR author dynamically.

The researcher would then open a PR that aims to modify the CRD template, or add a new one. Once merged we expect ArgoCD to detect the change, and create the CRD entity.

This will then cause the controller to start its active work.


## Deploy
In order to have it working, GitHub should be added as an Identity Provider on Keycloak.

Luckily there is an automation in place to take care of this. The only pre-requisite is a secret with the github app secret and client id. It can be created following the template below:
```sh
GH_SECRET=""
GH_CLIENT_ID=""
kubectl create secret generic github-app -n $NAMESPACE --from-literal "GH_SECRET=$GH_SECRET" --from-literal "GH_CLIENT_ID=$GH_CLIENT_ID"
```

The namespace the secret is created on should match the one used to install the federated node itself. It will be automatically copied to the relevent namespace.

Once the secret has been created set in the values file as follows:
```yaml
idp:
  github:
    secret_name: github-app
    secret_key: GH_SECRET
    clientid_key: GH_CLIENT_ID
    orgAndRepo: organization/repository
```
Of course, use the secret name and key names used in the bash command above.

One more secret (if applicable) to create is related to the additional result delivery destination that is not github.

Create a secret with whichever name you prefer, and then add the label with the url it should be used on.

To make it as broad as possible, the url should not include `http://` or `https://`. Basically the hostname.
```sh
secret_name="super-secret"
url=""
token=""

kubectl create secret generic -n fn-controller "${secret_name}" --from-literal="auth=${token}"

kubectl label secret "${secret_name}" -n fn-controller "url=${url}"
```


Then deploy as follows:

### STANDALONE

__note__ set the `namespace_name` environment variable to match the namespace name where the Federated Node has been deployed on. That's needed to automatically look for secrets/configmaps
```bash
cd k8s/fn-task-controller
helm install fncontroller . -f dev.values.yaml -n "${namespace_name}"
```
or though the helm repo:
```sh
helm repo add fn-task-controller https://aridhia-open-source.github.io/federated-node-task-controller

# Check available releases
helm search repo fn-task-controller --versions

# If you want to check development builds
helm search repo fn-task-controller --devel --versions

# Install
helm install fn-task-controller fn-task-controller/fn-task-controller -f <custom_value.yaml> --create-namespace --namespace=$namespace_name
```

### AS SUBCHART
When deployed with the Federated Node, only the secret has to be setup.

## Usage
There are 2 things to setup:
- ArgoCD monitoring the repository/branch where the CRD is stored (and subjected to the PR-pipeline process)
- Let the controller know where to find credentials details for the repo on where to push the results (can be some other than the previous step)

A github apps private key as a secret is required. Make sure the `.pem` file is named `key.pem`, and run the following to create a secret. Instead of `ghpk` it should be the a lowercase string with the format `organization`-`repository`.

You can use this snippet to format it:
```bash
python -c "import re; repository=input('Enter repo name:\n');print(re.sub(r'[\W_]+','-', repository.lower()))"
```

You will also need the client id from the github app so you can apply it as environment variable

```bash
CLIENT_ID="githubAppClientId"
kubectl create secret generic ghpk -n fn-controller --from-file scripts/key.pem --from-literal "GH_CLIENT_ID=$CLIENT_ID"
```
This allows the controller to be able to checkout the repository where the results should be pushed to.
