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
# Generate IDs of 4bytes size, 3 bytes incremental value + 1 byte for layer id.

import sys
from typing import Dict, Tuple

import yaml

from vss_tools.vspec.tree import VSSTreeNode
from vss_tools.vspec.vssexporters.utils import (
    get_trees,
    serialize_node_data,
)
import rich_click as click
import vss_tools.vspec.cli_options as clo
from pathlib import Path
from vss_tools import log
from vss_tools.vspec.utils import vss2id_val
from vss_tools.vspec.utils.idgen_utils import (
    fnv1_32_hash,
    get_all_keys_values,
    get_node_identifier_bytes,
)


def generate_split_id(
    node: VSSTreeNode, id_counter: int, strict_mode: bool
) -> Tuple[str, int]:
    """Generates static UIDs using 4-byte FNV-1 hash.

    @param node: VSSNode that we want to generate a static UID for
    @param id_counter: consecutive numbers counter for amount of nodes
    @param strict_mode: strict mode means case sensitivity for static UID generation
    @return: tuple of hashed string and id counter
    """

    if hasattr(node.data, "fka") and node.data.fka:  # type: ignore
        name = node.data.fka[0] if isinstance(node.data.fka, list) else node.data.fka  # type:  ignore
    else:
        name = node.get_fqn()
    node_data = serialize_node_data(node)
    identifier = get_node_identifier_bytes(
        name,
        node_data.get("datatype", ""),
        node.data.type.value,
        node_data.get("unit", ""),
        node_data.get("allowed", ""),
        node_data.get("min"),
        node_data.get("max"),
        strict_mode,
    )
    hashed_str = format(fnv1_32_hash(identifier), "08X")

    return hashed_str, id_counter + 1


def export_node(
    yaml_dict, node: VSSTreeNode, id_counter, strict_mode: bool
) -> Tuple[int, int]:
    """Recursive function to export the full tree to a dict

    @param yaml_dict: the to be exported dict
    @param node: parent node of the tree
    @param id_counter: counter for amount of ids
    @param strict_mode: strict mode means case sensitivity for static UID generation
    @return: id_counter, id_counter
    """

    node_id: str
    if not node.data.constUID:
        node_id, id_counter = generate_split_id(node, id_counter, strict_mode)
        node_id = f"0x{node_id}"
    else:
        log.info(
            f"Using const ID for {node.get_fqn()}. If you didn't mean "
            "to do that you can remove it in your vspec / overlay."
        )
        node_id = node.data.constUID

    # check for hash duplicates
    for key, value in get_all_keys_values(yaml_dict):
        if not isinstance(value, dict) and key == "staticUID":
            if node_id == value:
                log.fatal(
                    f"There is a small chance that the result of FNV-1 "
                    f"hashes are the same in this case the hash of node "
                    f"'{node.get_fqn()}' is the same as another hash."
                    f"Can you please update it."
                )
                # We could add handling of duplicates here
                sys.exit(-1)

    node_path = node.get_fqn()

    node_data = serialize_node_data(node)
    yaml_dict[node_path] = {"staticUID": f"{node_id}"}
    yaml_dict[node_path]["description"] = node.data.description
    yaml_dict[node_path]["type"] = str(node.data.type.value)
    if node_data.get("unit"):
        yaml_dict[node_path]["unit"] = node_data.get("unit")
    if node_data.get("datatype"):
        yaml_dict[node_path]["datatype"] = node_data.get("datatype")
    if node_data.get("allowed"):
        yaml_dict[node_path]["allowed"] = node_data.get("allowed")
    if node_data.get("min") is not None:
        yaml_dict[node_path]["min"] = node_data.get("min")
    if node_data.get("max") is not None:
        yaml_dict[node_path]["max"] = node_data.get("max")

    if node.data.fka:
        yaml_dict[node_path]["fka"] = node.data.fka

    if node.data.deprecation:
        yaml_dict[node_path]["deprecation"] = node.data.deprecation

    for child in node.children:
        id_counter, id_counter = export_node(yaml_dict, child, id_counter, strict_mode)

    return id_counter, id_counter


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
@click.option(
    "--validate-static-uid",
    type=click.Path(dir_okay=False, readable=True, exists=True),
    help="Validation file.",
)
@click.option("--validate-only", is_flag=True, help="Only validating. Not exporting.")
@click.option(
    "--case-sensitive",
    is_flag=True,
    help="Whether the generation of static UIDs is case-sensitive",
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
    validate_static_uid: Path,
    validate_only: bool,
    case_sensitive: bool,
):
    """
    Export as IDs.
    """
    tree, _ = get_trees(
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
    log.info("Generating vspec output including static UIDs...")

    id_counter: int = 0
    signals_yaml_dict: Dict[str, str] = {}  # Use str for ID values
    id_counter, _ = export_node(signals_yaml_dict, tree, id_counter, case_sensitive)

    if validate_static_uid:
        log.info(
            f"Now validating nodes, static UIDs, types, units and description with "
            f"file '{validate_static_uid}'"
        )

        validation_tree, _ = get_trees(
            (Path("."),),
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
        vss2id_val.validate_static_uids(signals_yaml_dict, validation_tree, strict)

    if not validate_only:
        with open(output, "w") as f:
            yaml.dump(signals_yaml_dict, f)
