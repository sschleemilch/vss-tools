from typing import Any, Callable

dynamic_datatypes: list[str] = []
dynamic_quantities: list[str] = []
dynamic_units: dict[str, list] = {}


class DatatypesException(Exception):
    pass


def is_xintx(value: Any, signed: bool, bits: int):
    values = [value]
    if isinstance(value, list):
        values = value

    for v in values:
        if not isinstance(v, int):
            return False
        if not signed and v < 0:
            return False
        max = 2**bits - 1
        min = 0
        if signed:
            max = 2 ** (bits - 1) - 1
            min = -(2 ** (bits - 1))
        if not (v <= max and v >= min):
            return False
    return True


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


def is_x(value: Any, c: type) -> bool:
    values = [value]
    if isinstance(value, list):
        values = value
    return all([isinstance(v, c) for v in values])


def is_bool(value: Any) -> bool:
    return is_x(value, bool)


def is_float(value: Any) -> bool:
    return is_x(value, float)


def is_string(value: Any) -> bool:
    return is_x(value, str)


def is_int(value: Any) -> bool:
    return is_x(value, int)


def is_numeric(value: Any) -> bool:
    return is_int(value) or is_float(value)


class Datatypes:
    UINT8 = "uint8", is_uint8, []
    UINT8_ARRAY = "uint8[]", is_uint8, []
    INT8 = "int8", is_int8, []
    INT8_ARRAY = "int8[]", is_int8, []
    UINT16 = "uint16", is_uint16, ["uint8"]
    UINT16_ARRAY = "uint16[]", is_uint16, ["uint8[]"]
    INT16 = "int16", is_int16, ["int8"]
    INT16_ARRAY = "int16[]", is_int16, ["int8[]"]
    UINT32 = "uint32", is_uint32, ["uint16", "uint8"]
    UINT32_ARRAY = "uint32[]", is_uint32, ["uint16[]", "uint8[]"]
    INT32 = "int32", is_int32, ["int16", "int8"]
    INT32_ARRAY = "int32[]", is_int32, ["int16[]", "int8[]"]
    UINT64 = "uint64", is_uint64, ["uint32", "uint16", "uint8"]
    UINT64_ARRAY = "uint64[]", is_uint64, ["uint32[]", "uint16[]", "uint8[]"]
    INT64 = "int64", is_int64, ["int32", "int16", "int8"]
    INT64_ARRAY = "int64[]", is_int64, ["int32[]", "int16[]", "int8[]"]
    BOOLEAN = "boolean", is_bool, []
    BOOLEAN_ARRAY = "boolean[]", is_bool, []
    FLOAT = "float", is_float, []
    FLOAT_ARRAY = "float[]", is_float, []
    DOUBLE = "double", is_float, []
    DOUBLE_ARRAY = "double[]", is_float, []
    STRING = "string", is_string, []
    STRING_ARRAY = "string[]", is_string, []
    NUMERIC = (
        "numeric",
        is_numeric,
        ["int64", "int32", "int16", "int8", "uint64", "uint32", "uint16", "uint8"],
    )
    NUMERIC_ARRAY = (
        "numeric[]",
        is_numeric,
        [
            "int64[]",
            "int32[]",
            "int16[]",
            "int8[]",
            "uint64[]",
            "uint32[]",
            "uint16[]",
            "uint8[]",
        ],
    )
    types = [
        UINT8,
        UINT8_ARRAY,
        INT8,
        INT8_ARRAY,
        UINT16,
        UINT16_ARRAY,
        INT16,
        INT16_ARRAY,
        UINT32,
        UINT32_ARRAY,
        INT32,
        INT32_ARRAY,
        UINT64,
        UINT64_ARRAY,
        INT64,
        INT64_ARRAY,
        BOOLEAN,
        BOOLEAN_ARRAY,
        FLOAT,
        FLOAT_ARRAY,
        DOUBLE,
        DOUBLE_ARRAY,
        STRING,
        STRING_ARRAY,
        NUMERIC,
        NUMERIC_ARRAY,
    ]

    @classmethod
    def get_type(cls, datatype: str) -> tuple[str, Callable, list[str]] | None:
        for t in cls.types:
            if datatype == t[0]:
                return t
        return None

    @classmethod
    def is_datatype(cls, value: Any, datatype: str) -> bool:
        t = cls.get_type(datatype)
        if t is None:
            raise DatatypesException(f"Unsupported datatype: {datatype}")
        return t[1](value)

    @classmethod
    def is_subtype_of(cls, check: str, base: str) -> bool:
        check_type = cls.get_type(check)
        if not check_type:
            raise DatatypesException(f"Not a valid type: '{check}'")
        base_type = cls.get_type(base)
        if not base_type:
            raise DatatypesException(f"Not a valid type: '{base}'")
        return check in base_type[2] or check == base


def get_all_datatypes() -> list[str]:
    static_datatypes = [t[0] for t in Datatypes.types]
    dynamic_array_datatypes = [f"{t}[]" for t in dynamic_datatypes]
    return static_datatypes + dynamic_datatypes + dynamic_array_datatypes


def is_array(datatype: str) -> bool:
    return datatype.endswith("[]")
