

class DepartmentValueError(Exception):
    """Raised when department is an empty string."""
    def __init__(self, message):
        self.message = message


class PersonValueError(Exception):
    """Raised when person is an empty string."""
    def __init__(self, message):
        self.message = message


class QualifierValueError(Exception):
    """Raised when qualifier is an empty string."""
    def __init__(self, message):
        self.message = message


class KeyValueError(Exception):
    """Raised when there is no corresponding file to the specified key."""
    def __init__(self, message):
        self.message = message


class BucketValueError(Exception):
    """Raised when bucket name is empty is empty string or incorrect."""
    def __init__(self, message):
        self.message = message


class S3ValueError(Exception):
    """Raised when credentials are incorrect."""
    def __init__(self, message):
        self.message = message


class SocketValueError(Exception):
    """Raise when host parameter is incorrect."""
    def __init__(self, message):
        self.message = message


class GlobalValueError(Exception):
    """Raise when host parameter is incorrect."""
    def __init__(self, message):
        self.message = message
