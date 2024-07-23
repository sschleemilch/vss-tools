#!/usr/bin/env python3
#
# Copyright (c) 2023 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0
#
# Convert vspec tree compatible JSON schema

import json
import rich_click as click
from vss_tools.vspec.model import VSSBranch, VSSStruct
from vss_tools.vspec.tree import VSSTreeNode
from vss_tools.vspec.vssexporters.utils import get_trees, serialize_node_data
import vss_tools.vspec.cli_options as clo
from pathlib import Path
from vss_tools import log
from typing import Dict, Any
from vss_tools.vspec.datatypes import Datatypes

type_map = {
    Datatypes.INT8[0]: "integer",
    Datatypes.UINT8[0]: "integer",
    Datatypes.INT16[0]: "integer",
    Datatypes.UINT16[0]: "integer",
    Datatypes.INT32[0]: "integer",
    Datatypes.UINT32[0]: "integer",
    Datatypes.INT64[0]: "integer",
    Datatypes.UINT64[0]: "integer",
    Datatypes.BOOLEAN[0]: "boolean",
    Datatypes.FLOAT[0]: "number",
    Datatypes.DOUBLE[0]: "number",
    Datatypes.STRING[0]: "string",
    Datatypes.INT8_ARRAY[0]: "array",
    Datatypes.UINT8_ARRAY[0]: "array",
    Datatypes.INT16_ARRAY[0]: "array",
    Datatypes.UINT16_ARRAY[0]: "array",
    Datatypes.INT32_ARRAY[0]: "array",
    Datatypes.UINT32_ARRAY[0]: "array",
    Datatypes.INT64_ARRAY[0]: "array",
    Datatypes.UINT64_ARRAY[0]: "array",
    Datatypes.BOOLEAN_ARRAY[0]: "array",
    Datatypes.FLOAT_ARRAY[0]: "array",
    Datatypes.DOUBLE_ARRAY[0]: "array",
    Datatypes.STRING_ARRAY[0]: "array",
}


def export_node(
    json_dict,
    node: VSSTreeNode,
    print_uuid,
    all_extended_attributes: bool,
    no_additional_properties: bool,
    require_all_properties: bool,
):
    """Preparing nodes for JSON schema output."""
    # keyword with X- sign are left for extensions and they are not part of official JSON schema
    json_dict[node.name] = {
        "description": node.data.description,
    }

    if hasattr(node.data, "datatype"):
        json_dict[node.name]["type"] = type_map[node.data.datatype]  # type: ignore

    # many optional attributes are initialized to "" in vsstree.py
    node_data = serialize_node_data(node)
    if node_data.get("min"):
        json_dict[node.name]["minimum"] = node_data.get("min")
    if node_data.get("max"):
        json_dict[node.name]["maximum"] = node_data.get("max")
    if node_data.get("allowed"):
        json_dict[node.name]["enum"] = node_data.get("allowed")
    if node_data.get("default"):
        json_dict[node.name]["default"] = node_data.get("default")

    if isinstance(node.data, VSSStruct):
        # change type to object
        json_dict[node.data.type.value]["type"] = "object"

    if all_extended_attributes:
        json_dict[node.name]["x-VSStype"] = str(node.data.type.value)
        if node_data.get("datatype"):
            json_dict[node.name]["x-datatype"] = node_data.get("datatype")
        if node.data.deprecation:
            json_dict[node.name]["x-deprecation"] = node.data.deprecation

        if node_data.get("unit"):
            json_dict[node.name]["x-unit"] = str(node_data.get("unit"))

        # TODO: What to do with aggregate? What is aggregate?
        # try:
        #     json_dict[node.name]["x-aggregate"] = node.aggregate
        #     if node.aggregate:
        #         # change type to object
        #         json_dict[node.type]["type"] = "object"
        # except AttributeError:
        #     pass

        if node.data.comment:
            json_dict[node.name]["x-comment"] = node.data.comment

        if print_uuid:
            json_dict[node.name]["x-uuid"] = node.uuid

    for field in node.get_additional_fields():
        json_dict[node.name][field] = node_data.get(field)

    # Generate child nodes
    if isinstance(node.data, VSSBranch) or isinstance(node.data, VSSStruct):
        if no_additional_properties:
            json_dict[node.name]["additionalProperties"] = False
        json_dict[node.name]["properties"] = {}
        if require_all_properties:
            json_dict[node.name]["required"] = [child.name for child in node.children]
        for child in node.children:
            export_node(
                json_dict[node.name]["properties"],
                child,
                print_uuid,
                all_extended_attributes,
                no_additional_properties,
                require_all_properties,
            )


@click.command()
@clo.vspec_opt
@clo.output_required_opt
@clo.include_dirs_opt
@clo.extended_attributes_opt
@clo.strict_opt
@clo.aborts_opt
@clo.uuid_opt
@clo.expand_opt
@clo.overlays_opt
@clo.quantities_opt
@clo.units_opt
@clo.types_opt
@clo.types_output_opt
@clo.extend_all_attributes_opt
@clo.pretty_print_opt
@click.option(
    "--no-additional-properties",
    is_flag=True,
    help="Do not allow properties not defined in VSS tree",
)
@click.option(
    "--require-all-properties",
    is_flag=True,
    help="Required all elements defined in VSS tree for a valid object",
)
def cli(
    vspec: Path,
    output: Path,
    include_dirs: tuple[Path],
    extended_attributes: tuple[str],
    strict: bool,
    aborts: tuple[str],
    uuid: bool,
    expand: bool,
    overlays: tuple[Path],
    quantities: tuple[Path],
    units: tuple[Path],
    types: tuple[Path],
    types_output: Path,
    extend_all_attributes: bool,
    pretty: bool,
    no_additional_properties: bool,
    require_all_properties: bool,
):
    """
    Export as a jsonschema.
    """
    tree, datatype_tree = get_trees(
        include_dirs,
        aborts,
        strict,
        extended_attributes,
        uuid,
        quantities,
        vspec,
        units,
        types,
        types_output,
        overlays,
        expand,
    )
    log.info("Generating JSON schema...")
    indent = None
    if pretty:
        log.info("Serializing pretty JSON schema...")
        indent = 2

    signals_json_schema: Dict[str, Any] = {}
    export_node(
        signals_json_schema,
        tree,
        uuid,
        extend_all_attributes,
        no_additional_properties,
        require_all_properties,
    )

    # Add data types to the schema
    if datatype_tree is not None:
        data_types_json_schema: Dict[str, Any] = {}
        export_node(
            data_types_json_schema,
            datatype_tree,
            uuid,
            extend_all_attributes,
            no_additional_properties,
            require_all_properties,
        )
        if extend_all_attributes:
            signals_json_schema["x-ComplexDataTypes"] = data_types_json_schema

    # VSS models only have one root, so there should only be one
    # key in the dict
    assert len(signals_json_schema.keys()) == 1
    top_node_name = list(signals_json_schema.keys())[0]
    signals_json_schema = signals_json_schema.pop(top_node_name)

    json_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": top_node_name,
        "type": "object",
        **signals_json_schema,
    }
    with open(output, "w", encoding="utf-8") as output_file:
        json.dump(json_schema, output_file, indent=indent, sort_keys=False)
