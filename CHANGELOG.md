# Releases Changelog

# 1.5.0

## Bugfix
- Fixed an issue with link user jobs name which could have ended up with invalid characters

# 1.4.0
- Prefixed all of the cluster-wide resources with the helm release name, granting uniqueness.
- Parameterized `CRD_GROUP` and `STORAGE_CLASS` in the analytics-operator
- Moved the controller's specific `ClusterRole` and bindings into namespaced ones

# 1.3.0

## Bugfix
- Fixed an issue that caused the controller to retry even when the review was pending

# 1.2.0
- Added a dynamic configuration to `global.taskReview` in the values files. This is only effective when deployed with the federated node. It will hold the result release until approved from the api, which in turns should set the task's CRD annotation `approved` to `"true"` and allowing result delivery. Defaults to `false`.

# 1.1.0
- Added support for AWS EFS persistent volume through the csi driver `efs.csi.aws.com`
    To configure it, set in the values file:
    ```yaml
    storage:
    aws:
        fileSystemId: <your EFS system ID>
        accessPointId: <Optional, access point id for better permission and isolation management in the EFS>
    ```

# 1.0.0
- Version 1.0.0 release. No changes. Only a version bump

## 0.7.4
- Changed the branch naming convention so it will be consistent with the user/task name

## 0.7.3
- Set the `kc-secrets` secret and `keycloak-config` configmap as conditional copy. Only if `global` is not empty in the values file.
    This will be taken care of by the FederatedNode parent chart

## 0.7.2
- Fixed alpine docker image to 3.19
- Added support on the CRD for database virtualization on the FN (available from Federated Node v1.0.0)
- Migrated away from python-alpine to python-slim for more consistency

## 0.7.1
- Added the `fnalpine.tag` to have a more dynamic way to set the docker tag for helper image.

## 0.7.0
### Bugfixes
- Fixed an issue on non-microk8s cluster where helper jobs were lacking proper permissions. Added the same account name as the controller.
- Increased timeout before removing a terminated helper job from 5s to 30s.
- Fixed an issue where the controller would lose connection after 5 minutes on AKS clusters
- Refactored the CRD approach so now it's a class, to centralize repeated operations
- Removed `dataset` field in the CRD as required
- Aggregated helper scripts in the new docker image `ghcr.io/aridhia-open-source/fn_task_controller_helper`
- Added a timeout in case a pod doesn't exist, leaving the controller hanging


## 0.6.0
- Changed the way the automatic delivery is performed. There is now only one choice, set as default path. Setting `delivery.github` or `delivery.other` will do so.

## 0.5.0
- Added support to deliver to defferent destinations. Without a matching secret this delivery will not work, even if it doesn't require auth.

## 0.4.1
- Fixed few inconsistencies with values fields.
- Fixed an issue whith azure storage, if the fileshare doesn't have the required folder, it will fail

## 0.4.0
- Support for multiple IdP from GitHub (use the `idp.github.orgAndRepo` to set the repository source in the format organizaiton/repository)

## 0.3.0
- Set the CRD as a cluster-level, not namespaced
- Added support for the dataset to be pinged by name too
- Added support to be run as a subchart

## 0.2.0
- Added a retry mechanism for any CRD failures, up to 5 times

## 0.1.1
- Integration with GitHub as IdP done automatically
- Some optimizations and refactors

## 0.0.1
- First release with basic functionalities
