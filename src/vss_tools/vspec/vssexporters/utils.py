# Copyright (c) 2023 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0

from vss_tools import log
from anytree import findall
from pathlib import Path
from vss_tools.vspec.tree import (
    VSSNode,
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
from vss_tools.vspec.model import VSSDataStruct


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
    overlays: tuple[Path, ...],
    expand: bool,
) -> tuple[VSSNode, VSSNode | None]:
    # BUG: Overlay cannot overwrite Branch that has instances correctly!!
    # Probably best:
    # - Load separately
    # - implmenet VSSTreeNode.merge()
    # - for overlay in overlay_tree: vspec_tree.merge(overlay)
    vspec_data = load_vspec(include_dirs, [vspec] + list(overlays) + list(types))

    if not quantities:
        quantities = (vspec.parent / "quantities.yaml",)
    if not units:
        units = (vspec.parent / "units.yaml",)

    quantity_data = load_quantities(list(quantities))
    dynamic_quantities.extend(list(quantity_data.keys()))
    unit_data = load_units(list(units))
    for k, v in unit_data.items():
        dynamic_units[k] = v.allowed_datatypes
        dynamic_units[v.unit] = v.allowed_datatypes

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
            filter_=lambda node: isinstance(node.data, VSSDataStruct),
        )
        dynamic_datatypes.extend([node.name for node in struct_nodes])
        if dynamic_datatypes:
            log.info(f"Dynamic datatypes: {len(dynamic_datatypes)}")

    return root, types_root
