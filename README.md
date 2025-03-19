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
Check the wiki page [How to deploy](https://github.com/Aridhia-Open-Source/federated-node-task-controller/wiki/How-to-deploy)

## Usage
Check the wiki page [Usage](https://github.com/Aridhia-Open-Source/federated-node-task-controller/wiki/How-to-deploy#usage)

## Result delivery
Check the wiki page [Automatic result delivery](https://github.com/Aridhia-Open-Source/federated-node-task-controller/wiki/Automatic-results-delivery)
