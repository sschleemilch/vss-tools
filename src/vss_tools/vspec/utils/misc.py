from typing import Any
import re


def getattr_nn(o: object, name: str, default: Any | None = None) -> Any:
    """
    Wraps getattr() but will also use 'default' if result is None
    """
    result = getattr(o, name, default)
    if result is None and default is not None:
        result = default
    return result


def camel_case(st):
    """Camel case string conversion"""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", st)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
    return re.sub(r"(?:^|_)([a-z])", lambda x: x.group(1).upper(), s2)


def camel_back(st):
    """Camel back string conversion"""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", st)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
    return re.sub(r"_([a-z])", lambda x: x.group(1).upper(), s2)
