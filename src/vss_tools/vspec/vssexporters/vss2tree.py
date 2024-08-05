# Copyright (c) 2024 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0

import vss_tools.vspec.cli_options as clo
from vss_tools.vspec.main import get_trees
import rich_click as click
from pathlib import Path
from anytree import RenderTree


@click.command()
@clo.vspec_opt
@clo.output_opt
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
@click.option(
    "--attr",
    "-a",
    help="Render tree by this attribute",
    default="name",
    show_default=True,
)
def cli(
    vspec: Path,
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
    output: Path | None,
    attr: str,
):
    """
    Export as YAML.
    """
    tree, datatype_tree = get_trees(
        vspec=vspec,
        include_dirs=include_dirs,
        aborts=aborts,
        strict=strict,
        extended_attributes=extended_attributes,
        uuid=uuid,
        quantities=quantities,
        units=units,
        types=types,
        overlays=overlays,
        expand=expand,
    )

    tree_content = RenderTree(tree).by_attr(attr)
    datatype_tree_content = ""
    if datatype_tree:
        datatype_tree_content = RenderTree(datatype_tree).by_attr(attr)

    if output:
        with open(output, "w") as f:
            f.write(tree_content)
            f.write(datatype_tree_content)
    else:
        print(tree_content)
        print(datatype_tree_content)
