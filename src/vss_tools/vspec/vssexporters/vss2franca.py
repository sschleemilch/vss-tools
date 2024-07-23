#!/usr/bin/env python3

# Copyright (c) 2021 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0

# Convert vspec tree to franca


import rich_click as click
from pathlib import Path
from vss_tools.vspec.tree import VSSTreeNode
from vss_tools.vspec.vssexporters.utils import get_trees, serialize_node_data
import vss_tools.vspec.cli_options as clo
from anytree import PreOrderIter  # type: ignore[import]

# Write the header line


def print_franca_header(file, version="unknown"):
    file.write(f"""
// Copyright (C) 2022, COVESA
//
// This program is licensed under the terms and conditions of the
// Mozilla Public License, version 2.0.  The full text of the
// Mozilla Public License is at https://www.mozilla.org/MPL/2.0/

const UTF8String VSS_VERSION = "{version}"

struct SignalSpec {{
    UInt32 id
    String name
    String type
    String description
    String datatype
    String unit
    Double min
    Double max
}}

const SignalSpec[] signal_spec = [
""")


# Write the data lines
def print_franca_content(file, tree, uuid):
    output = ""
    node: VSSTreeNode
    for node in PreOrderIter(tree):
        node_data = serialize_node_data(node)
        if node.parent:
            if output:
                output += ",\n{"
            else:
                output += "{"
            output += f'\tname: "{node.get_fqn()}"'
            output += f',\n\ttype: "{node.data.type.value}"'
            output += f',\n\tdescription: "{node.data.description}"'
            datatype = node_data.get("datatype")
            if datatype:
                output += f',\n\tdatatype: "{datatype}"'
            if uuid:
                output += f',\n\tuuid: "{node.uuid}"'
            unit = node_data.get("unit")
            if unit:
                output += f',\n\tunit: "{unit}"'
            min = node_data.get("min")
            if min:
                output += f",\n\tmin: {min}"
            max = node_data.get("max")
            if max:
                output += f",\n\tmax: {max}"
            allowed = node_data.get("allowed")
            if allowed:
                output += f",\n\tallowed: {allowed}"

            output += "\n}"
    file.write(output)


@click.command()
@clo.vspec_opt
@clo.output_required_opt
@clo.include_dirs_opt
@clo.extended_attributes_opt
@clo.strict_opt
@clo.aborts_opt
@clo.uuid_opt
@clo.overlays_opt
@clo.quantities_opt
@clo.units_opt
@click.option("--franca-vss-version", help="Adds franca version info.")
def cli(
    vspec: Path,
    output: Path,
    include_dirs: tuple[Path],
    extended_attributes: tuple[str],
    strict: bool,
    aborts: tuple[str],
    uuid: bool,
    overlays: tuple[Path],
    quantities: tuple[Path],
    units: tuple[Path],
    franca_vss_version: str,
):
    """
    Export as Franca.
    """
    print("Generating Franca output...")
    tree, _ = get_trees(
        include_dirs,
        aborts,
        strict,
        extended_attributes,
        uuid,
        quantities,
        vspec,
        units,
        tuple(),
        None,
        overlays,
        True,
    )
    outfile = open(output, "w")
    print_franca_header(outfile, franca_vss_version)
    print_franca_content(outfile, tree, uuid)
    outfile.write("\n]")
    outfile.close()
