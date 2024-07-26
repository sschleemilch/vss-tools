from pathlib import Path
from vss_tools.vspec.model import VSSUnit, VSSQuantity
from pydantic import ValidationError
import yaml
from vss_tools import log


def load_units_or_quantities(
    files: list[Path], class_type: type[VSSUnit | VSSQuantity]
) -> dict[str, VSSUnit | VSSQuantity]:
    data = {}
    for file in files:
        log.info(f"Loading {file} ('{class_type.__name__}')")
        content = yaml.safe_load(file.read_text())
        if not content:
            log.warning(f"{file}, empty")
            continue
        log.info(f"Elements loaded: {len(content)}")
        for k, v in content.items():
            try:
                data[k] = class_type(**v)
            except ValidationError as e:
                log.error(f"{k}: {e}")
                raise e
    return data


def load_units(unit_files: list[Path]) -> dict[str, VSSUnit]:
    return load_units_or_quantities(unit_files, VSSUnit)  # type: ignore[return-value]


def load_quantities(quantities: list[Path]) -> dict[str, VSSQuantity]:
    return load_units_or_quantities(quantities, VSSQuantity)  # type: ignore[return-value]
