# Copyright (c) 2023 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0

from vss_tools import log
from anytree import PreOrderIter, findall
from pathlib import Path
from vss_tools.vspec.model import (
    VSSDataBranch,
    VSSDataProperty,
    VSSDataStruct,
)
from vss_tools.vspec.tree import VSSNode, build_tree, RawNodeResolveException
from vss_tools.vspec.vspec import load_vspec
from vss_tools.vspec.units_quantities import load_quantities, load_units
from vss_tools.vspec.datatypes import (
    dynamic_units,
    dynamic_datatypes,
    dynamic_quantities,
)


class NameViolationException(Exception):
    pass


class ExtraAttributesException(Exception):
    pass


class MultipleTypeTreesException(Exception):
    pass


class RootTypesException(Exception):
    pass


class PropertyOrphansException(Exception):
    pass


def load_quantities_and_units(
    quantities: tuple[Path, ...], units: tuple[Path, ...], vspec_root: Path
) -> None:
    if not quantities:
        default_quantity = vspec_root / "quantities.yaml"
        if default_quantity.exists():
            quantities = (default_quantity,)
        else:
            log.warning(
                f"No 'quantity' files defined. Default not existing: {default_quantity.absolute()}"
            )
    if not units:
        default_unit = vspec_root / "units.yaml"
        if default_unit.exists():
            units = (default_unit,)
        else:
            log.warning(
                f"No 'unit' files defined. Default not existing: {default_unit.absolute()}"
            )

    quantity_data = load_quantities(list(quantities))
    dynamic_quantities.extend(list(quantity_data.keys()))
    unit_data = load_units(list(units))
    for k, v in unit_data.items():
        dynamic_units[k] = v.allowed_datatypes
        dynamic_units[v.unit] = v.allowed_datatypes


def check_name_violations(root: VSSNode, strict: bool, aborts: tuple[str, ...]) -> None:
    if strict or "name-style" in aborts:
        naming_violations = root.get_naming_violations()
        if naming_violations:
            for violation in naming_violations:
                log.error(f"Name violation: '{violation[0]}' ({violation[1]})")
            raise NameViolationException(
                f"Name violations detected: {naming_violations}"
            )


def check_extra_attribute_violations(
    root: VSSNode,
    strict: bool,
    aborts: tuple[str, ...],
    extended_attributes: tuple[str, ...],
) -> None:
    if extended_attributes:
        log.info(f"User defined extra attributes: {extended_attributes}")
    extra_attributes = root.get_extra_attributes(extended_attributes)
    for attribute in extra_attributes:
        log.warning(f"Unknown extra attribute: '{attribute[0]}':'{attribute[1]}'")
    if strict or "unknown-attribute" in aborts:
        if extra_attributes:
            raise ExtraAttributesException(
                f"Forbidden extra attributes detected: {extra_attributes}"
            )


def get_types_root(
    types: tuple[Path, ...], include_dirs: tuple[Path, ...]
) -> VSSNode | None:
    if not types:
        log.info("No user 'types' defined")
        return None

    types_root: VSSNode | None = None
    # We are iterating to be able to reference
    # types from earlier type files
    for types_file in list(types):
        data = load_vspec(include_dirs, [types_file])
        root, orphans = build_tree(data.data)
        if orphans:
            log.error(f"Types model has orphans\n{orphans}")
            exit(1)
        if types_root:
            node: VSSNode
            for node in PreOrderIter(root):
                if not types_root.connect(node.get_fqn(), node):
                    raise MultipleTypeTreesException()
        else:
            types_root = root

    if dynamic_datatypes:
        log.info(f"Dynamic datatypes added={len(dynamic_datatypes)}")
        log.debug(dynamic_datatypes)

    if not all(["." in t for t in dynamic_datatypes]):
        raise RootTypesException()

    if types_root:
        try:
            types_root.resolve()
        except RawNodeResolveException as e:
            log.critical(e)
            exit(1)

    return types_root


def get_invalid_node_msgs(root: VSSNode) -> list[str]:
    invalid_nodes = []
    for node in PreOrderIter(root):
        ok = True
        if node.parent is None:
            continue
        if isinstance(node.data, VSSDataProperty):
            if not isinstance(node.parent.data, VSSDataStruct):
                ok = False
        else:
            if not isinstance(node.parent.data, VSSDataBranch):
                ok = False
        if not ok:
            entry = f"'{node.get_fqn()} ({node.data.__class__.__name__})',"
            entry += f" invalid parent: '{node.parent.data.__class__.__name__}'"
            invalid_nodes.append(entry)
    return invalid_nodes


def validate_tree(root: VSSNode) -> None:
    invalid_node_msgs = get_invalid_node_msgs(root)
    if invalid_node_msgs:
        log.critical(f"Invalid nodes={len(invalid_node_msgs)}")
        for node in invalid_node_msgs:
            log.critical(node)
        exit(1)


def get_trees(
    vspec: Path,
    include_dirs: tuple[Path, ...] = tuple(),
    aborts: tuple[str, ...] = tuple(),
    strict: bool = False,
    extended_attributes: tuple[str, ...] = tuple(),
    uuid: bool = False,
    quantities: tuple[Path, ...] = tuple(),
    units: tuple[Path, ...] = tuple(),
    types: tuple[Path, ...] = tuple(),
    overlays: tuple[Path, ...] = tuple(),
    expand: bool = True,
) -> tuple[VSSNode, VSSNode | None]:
    load_quantities_and_units(quantities, units, vspec.parent)

    types_root = get_types_root(types, include_dirs)
    vspec_data = load_vspec(include_dirs, [vspec] + list(overlays))
    root, orphans = build_tree(vspec_data.data, connect_orphans=True)

    if orphans:
        log.error(f"Model has orphans\n{list(orphans.keys())}")
        exit(1)

    if expand:
        root.expand_instances()
    if uuid:
        root.add_uuids()

    try:
        root.resolve()
    except RawNodeResolveException as e:
        log.critical(e)
        exit(1)

    root.delete_nodes(findall(root, filter_=lambda n: n.get_vss_data().delete))

    validate_tree(root)

    if types_root:
        validate_tree(types_root)
        try:
            # TODO: Should type tree properties be compliant to name-style?
            # check_name_violations(types_root, strict, aborts)
            check_extra_attribute_violations(
                types_root, True, aborts, extended_attributes
            )
        except (NameViolationException, ExtraAttributesException):
            exit(1)

    try:
        check_name_violations(root, strict, aborts)
        check_extra_attribute_violations(root, strict, aborts, extended_attributes)
    except (NameViolationException, ExtraAttributesException):
        exit(1)

    return root, types_root
