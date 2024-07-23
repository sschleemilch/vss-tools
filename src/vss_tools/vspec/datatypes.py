from typing import Any

dynamic_datatypes: list[str] = []
dynamic_quantities: list[str] = []
dynamic_units: list[str] = []


class DatatypesException(Exception):
    pass


def is_xintx(value: Any, signed: bool, bits: int):
    if not isinstance(value, int):
        return False
    if not signed and value < 0:
        return False
    max = 2**bits - 1
    min = 0
    if signed:
        max = 2 ** (bits - 1) - 1
        min = -(2 ** (bits - 1))
    return value <= max and value >= min


def is_uint8(value: Any) -> bool:
    return is_xintx(value, False, 8)


def is_int8(value: Any) -> bool:
    return is_xintx(value, True, 8)


def is_uint16(value: Any) -> bool:
    return is_xintx(value, False, 16)


def is_int16(value: Any) -> bool:
    return is_xintx(value, True, 16)


def is_uint32(value: Any) -> bool:
    return is_xintx(value, False, 32)


def is_int32(value: Any) -> bool:
    return is_xintx(value, True, 32)


def is_uint64(value: Any) -> bool:
    return is_xintx(value, False, 64)


def is_int64(value: Any) -> bool:
    return is_xintx(value, True, 64)


def is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def is_float(value: Any) -> bool:
    return isinstance(value, float)


def is_string(value: Any) -> bool:
    return isinstance(value, str)


def is_numeric(value: Any) -> bool:
    return isinstance(value, int) or isinstance(value, float)


class Datatypes:
    UINT8 = "uint8", is_uint8
    INT8 = "int8", is_int8
    UINT16 = "uint16", is_uint16
    INT16 = "int16", is_int16
    UINT32 = "uint32", is_uint32
    INT32 = "int32", is_int32
    UINT64 = "uint64", is_uint64
    INT64 = "int64", is_int64
    BOOL = "boolean", is_bool
    FLOAT = "float", is_float
    DOUBLE = "double", is_float
    STRING = "string", is_string
    NUMERIC = "numeric", is_numeric
    types = [UINT8, INT8, UINT16, INT16, UINT32, INT32, UINT64, INT64, BOOL, FLOAT, DOUBLE, STRING, NUMERIC]

    @classmethod
    def get_type(cls, datatype: str) -> tuple[str, callable] | None:
        for t in cls.types:
            if datatype == t[0]:
                return t

    @classmethod
    def is_datatype(cls, value: Any, datatype: str) -> bool:
        t = cls.get_type(datatype.rstrip("[]"))
        if t is None:
            raise DatatypesException(f"Unsupported datatype: {datatype}")
        return t[1](value)


def get_all_datatypes() -> list[str]:
    static_datatypes = [t[0] for t in Datatypes.types]
    datatypes = static_datatypes + dynamic_datatypes
    datatypes += [f"{t}[]" for t in datatypes]
    return datatypes


def is_array(datatype: str) -> bool:
    return datatype.endswith("[]")
