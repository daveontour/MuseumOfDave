"""Service layer exceptions."""


class ServiceException(Exception):
    """Base exception for service layer."""
    
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(ServiceException):
    """Exception raised for validation failures."""
    
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class NotFoundError(ServiceException):
    """Exception raised when a resource is not found."""
    
    def __init__(self, message: str):
        super().__init__(message, status_code=404)


class ConflictError(ServiceException):
    """Exception raised for conflicts (e.g., processing already in progress)."""
    
    def __init__(self, message: str):
        super().__init__(message, status_code=409)
