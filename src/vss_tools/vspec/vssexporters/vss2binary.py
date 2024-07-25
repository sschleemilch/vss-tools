#!/usr/bin/env python3

# Copyright (c) 2022 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0

# Convert vspec tree to binary format

import ctypes
from pathlib import Path
from vss_tools import log
import vss_tools.vspec.cli_options as clo
import rich_click as click
from vss_tools.vspec.tree import VSSNode
from vss_tools.vspec.vssexporters.utils import get_trees
from vss_tools.vspec.model import VSSDataBranch, VSSDataDatatype


def allowedString(allowedList):
    allowedStr = ""
    for elem in allowedList:
        allowedStr += hexAllowedLen(elem) + elem
    return allowedStr


def hexAllowedLen(allowed):
    hexDigit1 = len(allowed) // 16
    hexDigit2 = len(allowed) - hexDigit1 * 16
    return "".join([intToHexChar(hexDigit1), intToHexChar(hexDigit2)])


def intToHexChar(hexInt):
    if hexInt < 10:
        return chr(hexInt + ord("0"))
    else:
        return chr(hexInt - 10 + ord("A"))


class Exporter:
    def export_vss_branch(
        self,
        vssdata: VSSDataBranch,
        name: str,
        output: str,
        n_children: int,
        cdll: ctypes.CDLL,
        uuid: str,
    ):
        cdll.createBinaryCnode(
            output.encode(),
            name.encode(),
            vssdata.type.value.encode(),
            uuid.encode(),
            vssdata.description.encode(),
            b"",
            b"",
            b"",
            b"",
            b"",
            b"",
            # TODO: How to handle "validate"? What is it?
            b"",
            n_children,
        )

    def export_vss_datatype(
        self,
        vssdata: VSSDataDatatype,
        name: str,
        output: str,
        n_children: int,
        cdll: ctypes.CDLL,
        uuid: str,
    ) -> None:
        cdll.createBinaryCnode(
            output.encode(),
            name.encode(),
            vssdata.type.value.encode(),
            uuid.encode(),
            vssdata.description.encode(),
            b"" if vssdata.datatype is None else vssdata.datatype.encode(),
            b"" if vssdata.min is None else str(vssdata.min).encode(),
            b"" if vssdata.max is None else str(vssdata.max).encode(),
            b"" if vssdata.unit is None else vssdata.unit.encode(),
            b"" if vssdata.allowed is None else allowedString(vssdata.allowed).encode(),
            b"" if vssdata.default is None else str(vssdata.default).encode(),
            # TODO: How to handle "validate"? What is it?
            b"",
            n_children,
        )


def export_node(cdll: ctypes.CDLL, node: VSSNode, generate_uuid, out_file: str):
    uuid = "" if node.uuid is None else node.uuid
    node.data.export(
        Exporter(),
        name=node.name,
        output=out_file,
        n_children=len(node.children),
        cdll=cdll,
        uuid=uuid,
    )
    for child in node.children:
        export_node(cdll, child, generate_uuid, out_file)


@click.command()
@clo.vspec_opt
@clo.output_required_opt
@click.option(
    "--bintool-dll",
    "-b",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
)
@clo.include_dirs_opt
@clo.extended_attributes_opt
@clo.strict_opt
@clo.aborts_opt
@clo.uuid_opt
@clo.overlays_opt
@clo.quantities_opt
@clo.units_opt
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
    bintool_dll: Path,
):
    """
    Export to Binary.
    """
    cdll = ctypes.CDLL(str(bintool_dll))
    cdll.createBinaryCnode.argtypes = (
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_int,
    )

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
        overlays,
        True,
    )
    log.info("Generating binary output...")
    export_node(cdll, tree, uuid, str(output))
    log.info(f"Binary output generated in {output}")
