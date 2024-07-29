# Copyright (c) 2023 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0

from vss_tools import log
from anytree import RenderTree, findall
from pathlib import Path
from vss_tools.vspec.tree import (
    VSSNode,
    build_trees,
    get_root_with_name,
)
from vss_tools.vspec.vspec import VSpec, load_vspec
from vss_tools.vspec.units_quantities import load_quantities, load_units
from vss_tools.vspec.datatypes import (
    dynamic_units,
    dynamic_datatypes,
    dynamic_quantities,
)
from vss_tools.vspec.model import VSSDataStruct


class NameViolationException(Exception):
    pass


class ExtraAttributesException(Exception):
    pass


def load_quantities_and_units(
    quantities: tuple[Path, ...], units: tuple[Path, ...], vspec_root: Path
) -> None:
    if not quantities:
        quantities = (vspec_root / "quantities.yaml",)
    if not units:
        units = (vspec_root / "units.yaml",)

    quantity_data = load_quantities(list(quantities))
    dynamic_quantities.extend(list(quantity_data.keys()))
    unit_data = load_units(list(units))
    for k, v in unit_data.items():
        dynamic_units[k] = v.allowed_datatypes
        dynamic_units[v.unit] = v.allowed_datatypes


def check_name_violations(root: VSSNode, strict: bool, aborts: tuple[str]) -> None:
    if strict or "name-style" in aborts:
        naming_violations = root.get_naming_violations()
        if naming_violations:
            for violation in naming_violations:
                log.error(f"Name violation: '{violation[0]}' ({violation[1]})")
            raise NameViolationException(
                f"Name violations detected: {naming_violations}"
            )


def check_extra_attribute_violations(
    root: VSSNode, strict: bool, aborts: tuple[str], extended_attributes: tuple[str]
) -> None:
    if strict or "unknown-attribute" in aborts:
        extra_attributes = root.get_extra_attributes(extended_attributes)
        if extra_attributes:
            for attribute in extra_attributes:
                log.error(
                    f"Forbidden extra attribute: '{
                        attribute[0]}':'{attribute[1]}'"
                )
            raise ExtraAttributesException(
                f"Forbidden extra attributes detected: {extra_attributes}"
            )


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
    vspec_data: VSpec = load_vspec(include_dirs, [vspec] + list(types))

    overlay_data: VSpec | None = None
    if overlays:
        overlay_data = load_vspec(include_dirs, list(overlays))

    load_quantities_and_units(quantities, units, vspec.parent)

    roots, orphans = build_trees(vspec_data.data)
    if orphans:
        log.error(f"Model has orphans\n{orphans}")
        exit(1)

    for r in roots:
        if expand:
            r.expand_instances()
        if uuid:
            r.add_uuids()

    overlay_roots: list[VSSNode] = []
    if overlay_data:
        log.info(f"Building overlay trees from {list(overlays)}")
        overlay_roots, overlay_orphans = build_trees(overlay_data.data, is_overlay=True)

        if len(overlay_roots) > 1:
            log.critical(f"Unexpected amount of overlay roots: {len(overlay_roots)}")
            log.critical(f"Overlay roots: {overlay_roots}")
            exit(1)

        if overlay_orphans:
            log.error(f"Overlay has orphans\n{overlay_orphans}")
            exit(1)

    if len(roots) > 2:
        log.critical(f"Unexpected amount of roots: {len(roots)}")
        log.critical(f"Roots: {roots}")
        exit(1)

    root = get_root_with_name(roots, "Vehicle")

    if not root:
        log.critical("Did not find 'Vehicle' root.")
        exit(1)

    if isinstance(root, VSSNode) and overlay_roots:
        log.info("Merging tree with overlay tree")
        root.merge(overlay_roots[0])

    try:
        check_name_violations(root, strict, aborts)
        check_extra_attribute_violations(root, strict, aborts, extended_attributes)
    except (NameViolationException, ExtraAttributesException):
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

    log.debug(RenderTree(root).by_attr())
    return root, types_root
