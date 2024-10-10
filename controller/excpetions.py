"""
Collection of exceptions. Only one for now, but it
follows the standard of the Federated Node backend
"""
class BaseControllerException(Exception):
    reason = None
    def __init__(self, reason='', *args: object) -> None:
        self.reason = reason
        super().__init__(*args)

class KeycloakException(BaseControllerException):
    pass

class FederatedNodeException(BaseControllerException):
    pass

class KubernetesException(BaseControllerException):
    pass
