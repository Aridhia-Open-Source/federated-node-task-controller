"""
Collection of exceptions. Only one for now, but it
follows the standard of the Federated Node backend
"""
class BaseControllerException(Exception):
    """
    Base class to raise custom exceptions, so we can
    control where the error messages are and generalize
    the catching
    """
    reason = None
    def __init__(self, *args: object) -> None:
        self.reason = args[0]
        super().__init__(*args)

class CRDException(BaseControllerException):
    """
    To be used in the keycloak helper
    """

class KeycloakException(BaseControllerException):
    """
    To be used in the keycloak helper
    """

class PodWatcherException(BaseControllerException):
    """
    To be used in the pod watcher helper
    """

class FederatedNodeException(BaseControllerException):
    """
    To be used in the task helper
    """

class KubernetesException(BaseControllerException):
    """
    To be used in the kubernetes helper
    """
