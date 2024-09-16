# Copyright (c) 2024 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0


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
struct_names: dict[str, int] = {}


def create_struct_names(root: VSSNode) -> None:
    for node in PreOrderIter(root):
        if node.name in struct_names:
            struct_names[node.name] += 1
        else:
            struct_names[node.name] = 1


def get_struct_name(node: VSSNode, types_tree: bool = False) -> str:
    if types_tree:
        return node.get_fqn("")
    split = node.get_fqn().split(".")
    parts = struct_names[node.name]
    if parts >= len(split):
        return node.get_fqn("")
    return "".join(split[-parts:])


def get_datatype(node: VSSNode, types_tree: bool = False) -> str:
    if isinstance(node.data, VSSDataDatatype):
        if node.data.datatype in datatype_map:
            return datatype_map[node.data.datatype]
        datatype = Datatypes.get_type(node.data.datatype)
        if datatype:
            return datatype[0]
        datatype_raw = node.data.datatype.replace(".", "")
        if is_array(datatype_raw):
            datatype_raw = f"[]{datatype_raw.rstrip('[]')}"
        return datatype_raw
    return get_struct_name(node, types_tree)


def add_go_struct(structs: dict[str, str], node: VSSNode, name: str, types_tree: bool = False):
    if isinstance(node.data, VSSDataBranch) or isinstance(node.data, VSSDataStruct):
        if not node.children:
            return ""
        struct = ""
        for child in node.children:
            child_datatype = get_datatype(child, types_tree)
            struct += f"\t{child.name} {child_datatype}\n"
            add_go_struct(structs, child, child_datatype, types_tree)
        if types_tree and isinstance(node.data, VSSDataBranch):
            pass
        else:
            structs[name] = struct


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
    if datatype_tree:
        add_go_struct(datatype_structs, datatype_tree, get_struct_name(datatype_tree, True), True)
    create_struct_names(tree)
    add_go_struct(structs, tree, get_struct_name(tree))

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
