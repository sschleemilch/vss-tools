#!/usr/bin/env python3

# Copyright (c) 2021 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0

# Convert vspec tree to CSV

import csv
from pathlib import Path
from vss_tools import log
import rich_click as click
import vss_tools.vspec.cli_options as clo
from vss_tools.vspec.tree import VSSNode
from vss_tools.vspec.vssexporters.utils import get_trees
from vss_tools.vspec.model import VSSDataBranch, VSSDataDatatype
from anytree import PreOrderIter  # type: ignore[import]
from typing import Any


def get_header(
    with_uuid: bool, entry_type: str, with_instance_column: bool
) -> list[str]:
    row = [
        entry_type,
        "Type",
        "DataType",
        "Deprecated",
        "Unit",
        "Min",
        "Max",
        "Desc",
        "Comment",
        "Allowed",
        "Default",
    ]
    if with_uuid:
        row.append("Id")
    if with_instance_column:
        row.append("Instances")
    return row


class Exporter:
    def export_vss_datatype(
        self,
        data: VSSDataDatatype,
        name: str,
        rows: list[list[Any]],
        with_uuid: bool,
        uuid: str | None,
        with_instance_column: bool,
    ):
        row = [
            name,
            data.type.value,
            data.datatype,
            "" if data.deprecation is None else data.deprecation,
            "" if data.unit is None else data.unit,
            "" if data.min is None else data.min,
            "" if data.max is None else data.max,
            data.description,
            "" if data.comment is None else data.comment,
            "" if data.allowed is None else data.allowed,
            "" if data.default is None else data.default,
        ]
        if with_uuid:
            row.append("" if uuid is None else uuid)
        row.append("")
        rows.append(row)

    def export_vss_data(
        self,
        data: VSSDataBranch,
        name: str,
        rows: list[list[Any]],
        with_uuid: bool,
        uuid: str | None,
        with_instance_column: bool,
    ):
        row = [
            name,
            data.type.value,
            "",
            "" if data.deprecation is None else data.deprecation,
            "",
            "",
            "",
            data.description,
            "" if data.comment is None else data.comment,
            "",
            "",
        ]
        if with_uuid:
            row.append("" if uuid is None else uuid)
        if with_instance_column:
            row.append("")
        rows.append(row)

    def export_vss_branch(
        self,
        data: VSSDataBranch,
        name: str,
        rows: list[list[Any]],
        with_uuid: bool,
        uuid: str | None,
        with_instance_column: bool,
    ):
        row = [
            name,
            data.type.value,
            "",
            "" if data.deprecation is None else data.deprecation,
            "",
            "",
            "",
            data.description,
            "" if data.comment is None else data.comment,
            "",
            "",
        ]
        if with_uuid:
            row.append("" if uuid is None else uuid)
        if with_instance_column:
            row.append("" if data.instances is None else data.instances)
        rows.append(row)


def add_rows(
    rows: list[list[Any]], root: VSSNode, with_uuid: bool, with_instance_column: bool
) -> None:
    for node in PreOrderIter(root):
        node.data.export(
            Exporter(),
            name=node.get_fqn(),
            with_uuid=with_uuid,
            with_instance_column=with_instance_column,
            uuid=node.uuid,
            rows=rows,
        )


def write_csv(rows: list[list[Any]], output: Path):
    with open(output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


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
):
    """
    Export as CSV.
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
        overlays,
        expand,
    )
    log.info("Generating CSV output...")

    generic_entry = datatype_tree and not types_output
    with_instance_column = not expand

    entry_type = "Node" if generic_entry else "Signal"
    rows = [get_header(uuid, entry_type, with_instance_column)]
    add_rows(rows, tree, uuid, with_instance_column)
    if generic_entry and datatype_tree:
        add_rows(rows, datatype_tree, uuid, with_instance_column)
    write_csv(rows, output)

    if not generic_entry and datatype_tree:
        rows = [get_header(uuid, "Node", with_instance_column)]
        add_rows(rows, datatype_tree, uuid, with_instance_column)
        write_csv(rows, types_output)
