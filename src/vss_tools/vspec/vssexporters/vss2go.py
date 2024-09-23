# Copyright (c) 2024 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0


from __future__ import annotations

from pathlib import Path

import rich_click as click
from anytree import PreOrderIter

import vss_tools.vspec.cli_options as clo
from vss_tools import log
from vss_tools.vspec.datatypes import Datatypes, is_array
from vss_tools.vspec.main import get_trees
from vss_tools.vspec.model import VSSDataBranch, VSSDataDatatype, VSSDataStruct
from vss_tools.vspec.tree import VSSNode

datatype_map = {
    Datatypes.INT8_ARRAY[0]: "[]int8",
    Datatypes.INT16_ARRAY[0]: "[]int16",
    Datatypes.INT32_ARRAY[0]: "[]int32",
    Datatypes.INT64_ARRAY[0]: "[]int64",
    Datatypes.UINT8_ARRAY[0]: "[]uint8",
    Datatypes.UINT16_ARRAY[0]: "[]uint16",
    Datatypes.UINT32_ARRAY[0]: "[]uint32",
    Datatypes.UINT64_ARRAY[0]: "[]uint64",
    Datatypes.FLOAT[0]: "float32",
    Datatypes.FLOAT_ARRAY[0]: "[]float32",
    Datatypes.DOUBLE[0]: "float64",
    Datatypes.DOUBLE_ARRAY[0]: "[]float64",
    Datatypes.STRING_ARRAY[0]: "[]string",
    Datatypes.NUMERIC[0]: "float64",
    Datatypes.NUMERIC_ARRAY[0]: "[]float64",
    Datatypes.BOOLEAN_ARRAY[0]: "[]bool",
    Datatypes.BOOLEAN[0]: "bool",
}


class NoInstanceRootException(Exception):
    pass


def get_instance_root(root: VSSNode, depth: int = 1) -> tuple[VSSNode, int]:
    if root.parent is None:
        raise NoInstanceRootException()
    if isinstance(root.parent.data, VSSDataBranch):
        if root.parent.data.is_instance:
            return get_instance_root(root.parent, depth + 1)
        else:
            return root.parent, depth
    else:
        raise NoInstanceRootException()


def add_children_map_entries(root: VSSNode, fqn: str, replace: str, map: dict[str, str]) -> None:
    child: VSSNode
    for child in root.children:
        child_fqn = child.get_fqn()
        map[child_fqn] = child_fqn.replace(fqn, replace)
        add_children_map_entries(child, fqn, replace, map)


def get_instance_mapping(root: VSSNode | None) -> dict[str, str]:
    if root is None:
        return {}
    instance_map: dict[str, str] = {}
    for node in PreOrderIter(root):
        if isinstance(node.data, VSSDataBranch):
            if node.data.is_instance:
                instance_root, depth = get_instance_root(node)
                new_name = instance_root.get_fqn() + "." + "I" + str(depth)
                fqn = node.get_fqn()
                instance_map[fqn] = new_name
                add_children_map_entries(node, fqn, new_name, instance_map)
    return instance_map


def get_datatype(node: VSSNode) -> str | None:
    """
    Gets the datatype string of a node.
    """
    datatype = None
    if isinstance(node.data, VSSDataDatatype):
        if node.data.datatype in datatype_map:
            return datatype_map[node.data.datatype]
        d = Datatypes.get_type(node.data.datatype)
        if d:
            datatype = d[0]
        # Struct type
        d_raw = node.data.datatype
        array = is_array(d_raw)
        struct_datatype = node.data.datatype.rstrip("[]")
        if array:
            struct_datatype = f"[]{struct_datatype}"
        datatype = struct_datatype
    return datatype


class GoStructMember:
    def __init__(self, name: str, datatype: str) -> None:
        self.name = name
        self.datatype = datatype


class GoStruct:
    def __init__(self, name: str) -> None:
        self.name = name
        self.members: list[GoStructMember] = []

    def __str__(self) -> str:
        r = f"type {self.name.replace('.', '')} struct {{\n"
        for member in self.members:
            r += f"\t{member.name} {member.datatype.replace('.', '')}\n"
        r += "}\n"
        return r

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GoStruct):
            return False
        return self.name == other.name


def get_struct_name(fqn: str, map: dict[str, str]) -> str:
    if fqn in map:
        return map[fqn]
    else:
        return fqn


def get_go_structs(root: VSSNode | None, map: dict[str, str], type_tree: bool = False) -> dict[str, GoStruct]:
    structs: dict[str, GoStruct] = {}
    if root is None:
        return structs
    for node in PreOrderIter(root):
        if isinstance(node.data, VSSDataBranch) or isinstance(node.data, VSSDataStruct):
            struct = GoStruct(get_struct_name(node.get_fqn(), map))
            for child in node.children:
                datatype = get_datatype(child)
                if not datatype:
                    datatype = get_struct_name(child.get_fqn(), map)
                member = GoStructMember(child.name, datatype)
                struct.members.append(member)
            if type_tree and isinstance(node.data, VSSDataBranch):
                pass
            else:
                structs[struct.name] = struct
    return structs


def get_prefixes(structs: dict[str, GoStruct]) -> list[str]:
    prefixes: dict[str, int] = {}
    for struct in structs.values():
        split = struct.name.split(".")
        if len(split) == 1:
            continue
        prefix = split[0]
        if prefix in prefixes:
            prefixes[prefix] += 1
        else:
            prefixes[prefix] = 1
    return [p for p, k in prefixes.items() if k > 1]


def get_prefix_strip_conflicts(prefix: str, structs: dict[str, GoStruct]) -> int:
    structs_new: list[str] = []
    for struct in structs.values():
        split = struct.name.split(".")
        sp = split[0]
        if len(split) == 1:
            structs_new.append(struct.name)
        else:
            if sp != prefix:
                structs_new.append(struct.name)
            else:
                log.debug(f"Stripping, {prefix=}, {struct.name=}")
                structs_new.append(".".join(split[1:]))
                log.debug(f"New name: {structs_new[-1]}")

    return len(structs_new) - len(set(structs_new))


def strip_structs_prefix(prefix: str, structs: dict[str, GoStruct]) -> int:
    stripped = 0
    for struct in structs.values():
        split = struct.name.split(".")
        if len(split) > 1:
            if split[0] == prefix:
                struct.name = ".".join(split[1:])
                stripped += 1
        for member in struct.members:
            dtsplit = member.datatype.split(".")
            if len(dtsplit) > 1:
                if dtsplit[0] == prefix:
                    member.datatype = ".".join(dtsplit[1:])
    return stripped


@click.command()
@clo.vspec_opt
@clo.output_required_opt
@clo.include_dirs_opt
@clo.extended_attributes_opt
@clo.strict_opt
@clo.aborts_opt
@clo.overlays_opt
@clo.quantities_opt
@clo.units_opt
@clo.types_opt
@click.option("--package", default="vss", help="Go package name", show_default=True)
@click.option("--short-names/--no-short-names", default=True, show_default=True, help="Shorten struct names")
def cli(
    vspec: Path,
    output: Path,
    include_dirs: tuple[Path],
    extended_attributes: tuple[str],
    strict: bool,
    aborts: tuple[str],
    overlays: tuple[Path],
    quantities: tuple[Path],
    units: tuple[Path],
    types: tuple[Path],
    package: str,
    short_names: bool,
):
    """
    Export as Go structs.
    """
    tree, datatype_tree = get_trees(
        vspec=vspec,
        include_dirs=include_dirs,
        aborts=aborts,
        strict=strict,
        extended_attributes=extended_attributes,
        quantities=quantities,
        units=units,
        types=types,
        overlays=overlays,
    )
    instance_map = get_instance_mapping(tree)
    structs = get_go_structs(tree, instance_map)
    log.info(f"Structs, amount={len(structs)}")
    datatype_structs = get_go_structs(datatype_tree, instance_map, True)
    log.info(f"Datatype structs, amount={len(datatype_structs)}")
    structs.update(datatype_structs)

    if short_names:
        rounds = 0
        while True:
            prefixes = get_prefixes(structs)
            log.debug(f"{prefixes=}")
            stripped = 0
            for prefix in prefixes:
                conflicts = get_prefix_strip_conflicts(prefix, structs)
                log.debug(f"Struct name conflicts, prefix={prefix}, conflicts={conflicts}")
                if conflicts == 0:
                    stripped += strip_structs_prefix(prefix, structs)
            if stripped == 0:
                break
            else:
                rounds += 1
        log.info(f"Name stripping, {rounds=}")

    with open(output, "w") as f:
        f.write(f"package {package}\n\n")
        for struct in structs.values():
            f.write(str(struct))
