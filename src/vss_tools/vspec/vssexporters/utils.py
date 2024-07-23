# Copyright (c) 2023 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0

from vss_tools import log
from anytree import findall, PreOrderIter
from pathlib import Path
from vss_tools.vspec.tree import (
    VSSTreeNode,
    build_trees,
    get_root_with_name,
)
from vss_tools.vspec.vspec import load_vspec
from vss_tools.vspec.units_quantities import load_quantities, load_units
from vss_tools.vspec.datatypes import (
    dynamic_units,
    dynamic_datatypes,
    dynamic_quantities,
)
from typing import Any
from vss_tools.vspec.model import VSSStruct
from vss_tools.vspec.vssexporters import IGNORE_KEYS_FOR_EXPORT


def serialize_node_data(
    node: VSSTreeNode, extra_attributes: bool = True
) -> dict[str, Any]:
    raw_data = dict(node.data)
    ignored_attributes = IGNORE_KEYS_FOR_EXPORT
    if not extra_attributes:
        ignored_attributes.extend(node.get_additional_fields())
    data = {
        k: v
        for k, v in raw_data.items()
        if v is not None and k not in ignored_attributes and v != []
    }

    data["type"] = data["type"].value
    return data


def node_as_flat_dict(
    root: VSSTreeNode, extra_attributes: bool = True
) -> dict[str, Any]:
    data = {}
    for node in PreOrderIter(root):
        key = node.get_fqn()
        data[key] = serialize_node_data(node, extra_attributes)
        if node.uuid:
            data[key]["uuid"] = node.uuid
    return data


def get_trees(
    include_dirs: tuple[Path],
    aborts: tuple[str],
    strict: bool,
    extended_attributes: tuple[str],
    uuid: bool,
    quantities: tuple[Path, ...],
    vspec: Path,
    units: tuple[Path, ...],
    types: tuple[Path, ...],
    types_output: Path | None,
    overlays: tuple[Path, ...],
    expand: bool,
) -> tuple[VSSTreeNode, VSSTreeNode | None]:
    vspec_data = load_vspec(include_dirs, [vspec] + list(overlays) + list(types))

    if not quantities:
        quantities = (vspec.parent / "quantities.yaml",)
    if not units:
        units = (vspec.parent / "units.yaml",)

    quantity_data = load_quantities(list(quantities))
    dynamic_quantities.extend(list(quantity_data.keys()))
    unit_data = load_units(list(units))
    dynamic_units.extend(list([unit.unit for unit in unit_data.values()]))
    dynamic_units.extend(list(unit_data.keys()))

    roots, orphans = build_trees(vspec_data.data)
    if orphans:
        log.error(f"Model has orphans\n{orphans}")
        exit(1)

    for r in roots:
        if expand:
            r.expand_instances()
        if uuid:
            r.add_uuids()

    if len(roots) > 2:
        log.critical(f"Unexpected amount of roots: {len(roots)}")
        log.critical(f"Roots: {roots}")
        exit(1)

    root = get_root_with_name(roots, "Vehicle")

    if not root:
        log.critical("Did not find 'Vehicle' root.")
        exit(1)

    if strict or "name-style" in aborts:
        naming_violations = root.get_naming_violations()
        if naming_violations:
            for violation in naming_violations:
                log.critical(f"Name violation: '{violation[0]}' ({violation[1]})")
            exit(1)

    if strict or "unknown-attribute" in aborts:
        additional_attributes = root.get_additional_attributes(extended_attributes)
        if additional_attributes:
            for attribute in additional_attributes:
                log.critical(
                    f"Additional forbidden attribute: '{attribute[0]}':'{attribute[1]}'"
                )
            exit(1)

    types_root = get_root_with_name(roots, "Types")

    if types_root:
        struct_nodes = findall(
            types_root,
            filter_=lambda node: isinstance(node.data, VSSStruct),
        )
        dynamic_datatypes.extend([node.name for node in struct_nodes])
        if dynamic_datatypes:
            log.info(f"Dynamic datatypes: {len(dynamic_datatypes)}")

    return root, types_root
