#!/usr/bin/env python3

# Copyright (c) 2022 Contributors to COVESA
#
# This program and the accompanying materials are made available under the
# terms of the Mozilla Public License 2.0 which is available at
# https://www.mozilla.org/en-US/MPL/2.0/
#
# SPDX-License-Identifier: MPL-2.0

import rich_click as click
from vss_tools import log
import vss_tools.vspec.cli_options as clo
from vss_tools.vspec.model import VSSDatatypeNode
from vss_tools.vspec.tree import VSSTreeNode
from vss_tools.vspec.vssexporters.utils import get_trees
from pathlib import Path
from vss_tools.vspec.utils.stringstyle import camel_back
from vss_tools.vspec.datatypes import Datatypes
from typing import Dict

from graphql import (
    GraphQLSchema,
    GraphQLObjectType,
    GraphQLField,
    GraphQLArgument,
    GraphQLNonNull,
    GraphQLString,
    GraphQLList,
    print_schema,
    GraphQLInt,
    GraphQLFloat,
    GraphQLBoolean,
)

GRAPHQL_TYPE_MAPPING = {
    Datatypes.INT8[0]: GraphQLInt,
    Datatypes.INT8_ARRAY[0]: GraphQLList(GraphQLInt),
    Datatypes.UINT8[0]: GraphQLInt,
    Datatypes.UINT8_ARRAY[0]: GraphQLList(GraphQLInt),
    Datatypes.INT16[0]: GraphQLInt,
    Datatypes.INT16_ARRAY[0]: GraphQLList(GraphQLInt),
    Datatypes.UINT16[0]: GraphQLInt,
    Datatypes.UINT16_ARRAY[0]: GraphQLList(GraphQLInt),
    Datatypes.INT32[0]: GraphQLInt,
    Datatypes.INT32_ARRAY[0]: GraphQLList(GraphQLInt),
    Datatypes.UINT32[0]: GraphQLFloat,
    Datatypes.UINT32_ARRAY[0]: GraphQLList(GraphQLFloat),
    Datatypes.INT64[0]: GraphQLFloat,
    Datatypes.INT64_ARRAY[0]: GraphQLList(GraphQLFloat),
    Datatypes.UINT64[0]: GraphQLFloat,
    Datatypes.UINT64_ARRAY[0]: GraphQLList(GraphQLFloat),
    Datatypes.FLOAT[0]: GraphQLFloat,
    Datatypes.FLOAT_ARRAY[0]: GraphQLList(GraphQLFloat),
    Datatypes.DOUBLE[0]: GraphQLFloat,
    Datatypes.DOUBLE_ARRAY[0]: GraphQLList(GraphQLFloat),
    Datatypes.BOOLEAN[0]: GraphQLBoolean,
    Datatypes.BOOLEAN_ARRAY[0]: GraphQLList(GraphQLBoolean),
    Datatypes.STRING[0]: GraphQLString,
    Datatypes.STRING_ARRAY[0]: GraphQLList(GraphQLString),
}


class GraphQLFieldException(Exception):
    pass


def get_schema_from_tree(root_node: VSSTreeNode, additional_leaf_fields: list) -> str:
    """Takes a VSSNode and additional fields for the leafs. Returns a graphql schema as string."""
    args = dict(
        id=GraphQLArgument(
            GraphQLNonNull(GraphQLString),
            description="VIN of the vehicle that you want to request data for.",
        ),
        after=GraphQLArgument(
            GraphQLString,
            description=(
                "Filter data to only provide information that was sent "
                "from the vehicle after that timestamp."
            ),
        ),
    )

    root_query = GraphQLObjectType(
        "Query",
        lambda: {
            "vehicle": GraphQLField(
                to_gql_type(root_node, additional_leaf_fields), args
            )
        },
    )
    return print_schema(GraphQLSchema(root_query))


def to_gql_type(node: VSSTreeNode, additional_leaf_fields: list) -> GraphQLObjectType:
    if isinstance(node.data, VSSDatatypeNode):
        fields = leaf_fields(node, additional_leaf_fields)
    else:
        fields = branch_fields(node, additional_leaf_fields)
    return GraphQLObjectType(
        name=node.get_fqn("_"),
        fields=fields,
        description=node.data.description,
    )


def leaf_fields(
    node: VSSTreeNode, additional_leaf_fields: list
) -> Dict[str, GraphQLField]:
    field_dict = {}
    if node.data.datatype is not None:  # type: ignore
        field_dict["value"] = field(
            node,
            "Value: ",
            GRAPHQL_TYPE_MAPPING[node.data.datatype],  # type: ignore
        )
    field_dict["timestamp"] = field(node, "Timestamp: ")
    if additional_leaf_fields:
        for additional_field in additional_leaf_fields:
            if len(additional_field) == 2:
                field_dict[additional_field[0]] = field(
                    node, f" {str(additional_field[1])}: "
                )
            else:
                raise GraphQLFieldException(
                    "", "", "Incorrect format of graphql field specification"
                )
    if node.data.unit:  # type: ignore
        field_dict["unit"] = field(node, "Unit of ")
    return field_dict


def branch_fields(
    node: VSSTreeNode, additional_leaf_fields: list
) -> Dict[str, GraphQLField]:
    valid = (c for c in node.children if len(c.children) or hasattr(c.data, "datatype"))
    return {
        camel_back(c.name): field(c, type=to_gql_type(c, additional_leaf_fields))
        for c in valid
    }


def field(node: VSSTreeNode, description_prefix="", type=GraphQLString) -> GraphQLField:
    return GraphQLField(
        type,
        deprecation_reason=node.data.deprecation or None,
        description=f"{description_prefix}{node.data.description}",
    )


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
@click.option(
    "--gql-fields",
    "-g",
    multiple=True,
    help="""
        Add additional fields to the nodes in the graphql schema.
        Usage: '<field_name>,<description>'",
    """,
)
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
    gql_fields: list[str],
):
    """
    Export as GraphQL.
    """
    tree, _ = get_trees(
        include_dirs,
        aborts,
        strict,
        extended_attributes,
        False,
        quantities,
        vspec,
        units,
        tuple(),
        None,
        overlays,
        True,
    )
    log.info("Generating graphql output...")
    outfile = open(output, "w")
    gqlfields: list[list[str]] = []
    for field in gql_fields:
        gqlfields.append(field.split(","))
    outfile.write(get_schema_from_tree(tree, gqlfields))
    outfile.write("\n")
    outfile.close()
