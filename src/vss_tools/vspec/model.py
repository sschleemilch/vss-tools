from enum import Enum
from typing import Any, Self
import re

from pydantic import (
    BaseModel,
    ValidationError,
    field_validator,
    model_validator,
    Field,
    ConfigDict,
)

from vss_tools import log
from vss_tools.vspec.datatypes import (
    Datatypes,
    dynamic_quantities,
    dynamic_units,
    get_all_datatypes,
    is_array,
)


class ModelException(Exception):
    pass


class NodeType(str, Enum):
    BRANCH = "branch"
    ATTRIBUTE = "attribute"
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    STRUCT = "struct"
    PROPERTY = "property"


class VSSNode(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: NodeType
    description: str
    comment: str | None = None
    delete: bool = False
    deprecation: str | None = None
    constUID: str | None = None
    fka: list[str] = []

    @field_validator("constUID")
    @classmethod
    def check_const_uid_format(cls, v: str) -> str:
        pattern = r"^0x[0-9A-Fa-f]{8}$"
        assert bool(re.match(pattern, v))
        return v


class VSSBranch(VSSNode):
    instances: list[str | list[Any]] = []


class VSSUnit(BaseModel):
    definition: str
    unit: str
    quantity: str
    allowed_datatypes: list[str] = Field(alias="allowed-datatypes")

    @field_validator("quantity")
    @classmethod
    def check_valid_quantity(cls, v: str) -> str:
        assert v in dynamic_quantities, f"Invalid quantity: {v}"
        return v

    @field_validator("allowed_datatypes")
    @classmethod
    def check_valid_datatypes(cls, values: list[str]) -> list[str]:
        datatypes = get_all_datatypes()
        for value in values:
            assert value in datatypes, f"Invalid datatype: {value}"
        return values


class VSSQuantity(BaseModel):
    definition: str
    comment: str | None = None
    remark: str | None = None


class VSSDatatypeNode(VSSNode):
    datatype: str
    arraysize: int | None = None
    min: int | float | None = None
    max: int | float | None = None
    unit: str | None = None
    allowed: list[str | int | float | bool] | None = None
    default: list[str | int | float | bool] | str | int | float | bool | None = None

    @model_validator(mode="after")
    def check_type_arraysize_consistency(self) -> Self:
        if self.arraysize is not None:
            assert is_array(
                self.datatype
            ), f"'arraysize' set on a non array datatype: '{self.datatype}'"
        return self

    @model_validator(mode="after")
    def check_type_default_consistency(self) -> Self:
        if self.default is not None:
            if is_array(self.datatype):
                assert isinstance(
                    self.default, list
                ), f"'default' with type {type(self.default)} does not match datatype '{self.datatype}'"
                if self.arraysize:
                    assert (
                        len(self.default) == self.arraysize
                    ), "'default' array size does not match 'arraysize'"
            else:
                assert not isinstance(
                    self.default, list
                ), f"'default' with type {type(self.default)} does not match datatype '{self.datatype}'"
        return self

    @model_validator(mode="after")
    def check_default_values_allowed(self) -> Self:
        if self.default and self.allowed:
            values = self.default
            if not isinstance(self.default, list):
                values = [self.default]
            for v in values:  # type: ignore
                assert (
                    v in self.allowed
                ), f"default value '{v}' is not in 'allowed' list"
        return self

    @model_validator(mode="after")
    def check_allowed_datatype_consistency(self) -> Self:
        if self.allowed:
            for v in self.allowed:
                assert Datatypes.is_datatype(
                    v, self.datatype
                ), f"{v} is not of type {self.datatype}"
        return self

    @model_validator(mode="after")
    def check_allowed_min_max(self) -> Self:
        err = "'min/max' and 'allowed' cannot be used together"
        if self.allowed is not None:
            assert self.min is None and self.max is None, err
        if self.min is not None or self.max is not None:
            assert self.allowed is None, err
        return self

    @field_validator("datatype")
    @classmethod
    def check_datatype(cls, v: str) -> str:
        assert v in get_all_datatypes(), f"{v} is not a valid datatype"
        return v

    @field_validator("unit")
    @classmethod
    def check_valid_unit(cls, v: str) -> str:
        assert v in dynamic_units, f"{v} is not a valid unit"
        return v


class VSSProperty(VSSDatatypeNode):
    pass


class VSSSensorActuator(VSSDatatypeNode):
    pass


class VSSStruct(VSSNode):
    pass


class VSSAttribute(VSSDatatypeNode):
    pass


TYPE_CLASS_MAP = {
    NodeType.BRANCH: VSSBranch,
    NodeType.ATTRIBUTE: VSSAttribute,
    NodeType.SENSOR: VSSSensorActuator,
    NodeType.ACTUATOR: VSSSensorActuator,
    NodeType.STRUCT: VSSStruct,
    NodeType.PROPERTY: VSSProperty,
}


def get_model(data: dict[str, Any], name: str) -> VSSNode:
    try:
        model = VSSNode(**data)
        cls = TYPE_CLASS_MAP.get(model.type)
        if not cls:
            msg = f"No class type mapping for '{model.type}'"
            log.critical(msg)
            raise ModelException(msg)
        model = cls(**data)
    except ValidationError as e:
        log.error(f"'{name}': {e}")
        raise e

    return model
