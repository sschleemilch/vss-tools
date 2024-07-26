from typing import Any


def getattr_nn(o: object, name: str, default: Any | None = None) -> Any:
    """
    Wraps getattr() but will also use 'default' if result is None
    """
    result = getattr(o, name, default)
    if result is None and default is not None:
        result = default
    return result
