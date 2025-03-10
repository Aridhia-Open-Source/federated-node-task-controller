# Releases Changelog

## 0.4.0
- Support for multiple IdP from GitHub (use the `idp.github.orgAndRepo` to set the repository source in the format organizaiton/repository)
- Added support to deliver to defferent destinations. Without a matching secret this delivery will not work, even if it doesn't require auth.

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
