# Federated Node Task Controller (FNTC)

For the time being is on a separate repo, it might get merged in the main Federated Node one: [PHEMS_federated_node](https://github.com/Aridhia-Open-Source/PHEMS_federated_node)


This python controller aims to monitor a CRD which is defined in [this manifest](./k8s/crd.yaml) and translate it into an internal request to the federated node to `POST /tasks`.

After creating a task successfully, it will periodically check for the status and (TODO) push the results, once the pod completes, ideally outside the environment.

### Assumptions
GitHub should be set as IdP (Identity Provider) in the FN keycloak, so that the user that triggers the task from GH, can be mapped with the internal permission system, basically acting as a bridge between analytics code and the Data Permission Platform.

### How does this work?
Let's imagine that the source code to run some analytics is hosted in github in repo `average_analysis`.

In this repo there will be a folder where the CRD defined [here](./k8s/crd.yaml) is hosted as template.

ArgoCD will start monitoring this repo on a dedicated branch, set to read-only for all users, except the Admins.

There will also be a pipeline (i.e [example](./pipeline-template.yml)) that refers to another actions template (provided by us), which takes care of (upon merge to a user-defined branch) merging the CRD changes to a third branch (i.e. `monitor`) which ArgoCD is monitoring for changes. It also injects the username on the PR author dynamically.

The researcher would then open a PR that aims to modify the CRD template, or add a new one. Once merged we expect ArgoCD to detect the change, and create the CRD entity.

This will then cause the controller to start its active work.

### Future dev
- Aiming to have the automatic push from the controller (either via a separate job or within its process) of the results to an agreed destination. At the moment, we're trying GitHub itself.


## Deploy
Needs a github apps private key as a secret. Make sure the `.pem` file is named `key.pem`, and run the following to create a secret. Instead of `ghpk` it should be the a lowercase string with the format `organization`-`repository`.

You can use this snippet to format it:
```bash
python -c "import re; repository=input('Enter repo name:\n');print(re.sub(r'[\W_]+','-', repository.lower()))"
```

You will also need the client id from the github app so you can apply it as environment variable

```bash
CLIENT_ID="Iv23lis6Qfwf5bXS9iaU"
kubectl create secret generic aridhia-open-source-federated-node-example-app -n controller --from-file scripts/key.pem --from-literal "GH_CLIENT_ID=$CLIENT_ID"
```
Very straightforward
```bash
kubectl apply k8s/
```
