# Copyright (c) 2024 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0


import re
from io import TextIOWrapper
from pathlib import Path

import rich_click as click
from anytree import PreOrderIter

import vss_tools.vspec.cli_options as clo
from vss_tools.vspec.datatypes import Datatypes, is_array
from vss_tools.vspec.main import get_trees
from vss_tools.vspec.model import VSSDataBranch, VSSDataDatatype, VSSDataStruct
from vss_tools.vspec.tree import VSSNode

datatype_map = {
    Datatypes.INT8_ARRAY[0]: "[]int ",
    Datatypes.INT16_ARRAY[0]: "[]int",
    Datatypes.INT32_ARRAY[0]: "[]int",
    Datatypes.INT64_ARRAY[0]: "[]int",
    Datatypes.UINT8_ARRAY[0]: "[]uint",
    Datatypes.UINT16_ARRAY[0]: "[]uint",
    Datatypes.UINT32_ARRAY[0]: "[]uint",
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
# Instance names containing the prefix as key, the instance part as name
# E.g. Vehicle.Cabin.Door: Row1.DriverSide
instance_names: dict[str, list[str]] = {}


class ToplevelInstanceException(Exception):
    pass


def add_instance_name(node: VSSNode | None, name: str = ""):
    if node is None:
        raise ToplevelInstanceException(name)
    if isinstance(node.data, VSSDataBranch):
        if node.data.is_instance:
            n = node.name
            if name:
                n += "." + name
            add_instance_name(node.parent, n)
        else:
            fqn = node.get_fqn()
            if fqn in instance_names:
                instance_names[fqn].append(name)
            else:
                instance_names[fqn] = [name]


def add_instance_names(root: VSSNode | None):
    if root is None:
        return
    for node in PreOrderIter(root):
        if isinstance(node.data, VSSDataBranch):
            if node.data.is_instance:
                add_instance_name(node)


def get_longest_instance_match(node: VSSNode) -> str | None:
    match = None
    for prefix, inames in instance_names.items():
        if node.get_fqn().startswith(prefix):
            for iname in inames:
                if iname in node.get_fqn():
                    if match is None:
                        match = iname
                    else:
                        if len(iname) > len(match):
                            match = iname
    return match


def strip_instances(node: VSSNode) -> str:
    name = node.get_fqn()
    match = get_longest_instance_match(node)
    stripped = ""
    if match:
        stripped = name.replace(match, "")
    if stripped:
        name = stripped
    name = name.rstrip(".")
    return name


def get_struct_name(node: VSSNode, structs: dict[str, str]) -> str:
    struct_name = strip_instances(node)
    while struct_name in structs:
        struct_name = increment_name(struct_name)
    return struct_name


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


def increment_name(name: str) -> str:
    match = re.search(r"(\d+)$", name)
    incremented = name + "2"
    if match:
        value = match[0]
        incremented = name[: -len(value)] + str(int(value) + 1)
    return incremented


def add_structs(structs: dict[str, str], node: VSSNode, name: str, types_tree: bool = False):
    """
    Traverses the tree and builds structs with a dict with struct name as key and
    the struct content as value
    """
    if isinstance(node.data, VSSDataBranch) or isinstance(node.data, VSSDataStruct):
        if not node.children:
            return ""
        struct = ""
        child_structs: dict[str, list[VSSNode]] = {}
        for child in node.children:
            child_datatype = get_datatype(child)
            if child_datatype:
                struct += f"\t{child.name} {child_datatype}\n"
            else:
                child_struct_name = get_struct_name(child, structs)
                struct += f"\t{child.name} {child_struct_name}\n"
                if child_struct_name in child_structs:
                    child_structs[child_struct_name].append(child)
                else:
                    child_structs[child_struct_name] = [child]
        if types_tree and isinstance(node.data, VSSDataBranch):
            pass
        else:
            structs[name] = struct
        for struct_name, childs in child_structs.items():
            for child in childs:
                add_structs(structs, child, struct_name, types_tree)


def get_struct_name_count(structs: dict[str, str]) -> dict[str, int]:
    mapping = {}
    for struct_name in structs:
        name = struct_name.split(".")[-1]
        if name in mapping:
            mapping[name] += 1
        else:
            mapping[name] = 1
    return mapping


def get_struct_map(structs: dict[str, str], name_count: dict[str, int]) -> dict[str, str]:
    map = {}
    for fqn in structs:
        split = fqn.split(".")
        name = split[-1]
        parts = name_count[name]
        if parts > len(split):
            map[fqn] = fqn
        else:
            map[fqn] = ".".join(split[-parts:])
    return map


def build_final_structs(structs: dict[str, str], struct_map: dict[str, str]) -> dict[str, str]:
    shortened = {}
    for fqn, content in structs.items():
        new_content = content
        content_lines = content.splitlines()
        for line in content_lines:
            datatype = line.split()[-1]
            if datatype in struct_map:
                new_content = new_content.replace(datatype, struct_map[datatype])
        new_name = struct_map[fqn].replace(".", "")
        new_content = new_content.replace(".", "")
        shortened[new_name] = new_content
    return shortened


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
@clo.types_output_opt
@click.option("--package", default="vss", help="Go package name", show_default=True)
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
    types_output: Path | None,
    package: str,
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
    structs: dict[str, str] = {}
    datatype_structs: dict[str, str] = {}
    add_instance_names(tree)
    add_instance_names(datatype_tree)
    if datatype_tree:
        add_structs(datatype_structs, datatype_tree, get_struct_name(datatype_tree, datatype_structs), True)
    add_structs(structs, tree, get_struct_name(tree, structs))

    # struct_name_count = get_struct_name_count(structs)
    # struct_map = get_struct_map(structs, struct_name_count)
    # structs = build_final_structs(structs, struct_map)

    with open(output, "w") as f:
        f.write(f"package {package}\n\n")
        write_structs(structs, f)
        if not types_output:
            write_structs(datatype_structs, f)

    if types_output:
        with open(types_output, "w") as f:
            f.write(f"package {package}\n\n")
            write_structs(datatype_structs, f)


def write_structs(structs: dict[str, str], fd: TextIOWrapper) -> None:
    for name, content in structs.items():
        fd.write(f"type {name} struct {{\n{content}}}\n")
