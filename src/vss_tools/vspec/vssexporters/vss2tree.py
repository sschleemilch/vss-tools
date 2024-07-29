import vss_tools.vspec.cli_options as clo
from vss_tools.vspec.vssexporters.utils import get_trees
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

    tree_content = RenderTree(tree).by_attr()
    datatype_tree_content = ""
    if datatype_tree:
        datatype_tree_content = RenderTree(datatype_tree).by_attr()

    if output:
        with open(output, "w") as f:
            f.write(tree_content)
            f.write(datatype_tree_content)
    else:
        print(tree_content)
        print(datatype_tree_content)
