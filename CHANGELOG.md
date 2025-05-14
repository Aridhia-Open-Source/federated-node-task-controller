# Releases Changelog

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
