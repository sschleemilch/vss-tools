import re
from typing import Any

from anytree import Node, PreOrderIter, findall
from copy import deepcopy

from vss_tools import log
from vss_tools.vspec.model import VSSDatatypeNode, get_model, VSSBranch
from vss_tools.vspec.datatypes import Datatypes

SEPARATOR = "."


class NoRootsException(Exception):
    pass


class InvalidExpansionEntryException(Exception):
    pass


class VSSTreeNode(Node):  # type: ignore[misc]
    separator = SEPARATOR

    def __init__(self, name: str, data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        log.debug(f"VSSTreeNode, name={name}")
        self.data = get_model(data, name)


def get_expected_parent(name: str) -> str | None:
    parent = SEPARATOR.join(name.split(SEPARATOR)[:-1])
    if parent == name:
        return None
    return parent


def get_name(key: str) -> str:
    return key.split(SEPARATOR)[-1]


def find_children_ids(node_ids: list[str], name: str) -> list[str]:
    ids = []
    for i in node_ids:
        if get_expected_parent(i) == name:
            ids.append(i)
    return ids


def get_naming_violations(root: VSSTreeNode) -> list[str]:
    violations = []
    log.info(f"Checking node name compliance for {root.name}")
    camel_case_pattern = re.compile("[A-Z][A-Za-z0-9]*$")
    for node in PreOrderIter(root):
        match = re.match(camel_case_pattern, node.name)
        if not match:
            violations.append([node.name, "not CamelCase"])
        if isinstance(node.data, VSSDatatypeNode):
            if node.data.datatype == Datatypes.BOOL[0]:
                if not node.name.startswith("Is"):
                    violations.append([node.name, "Not starting with 'Is'"])
    if violations:
        log.info(f"Naming violations: {len(violations)}")
    return violations


def get_additional_fields(node: VSSTreeNode) -> list[str]:
    model = node.data
    defined_fields = model.model_fields.keys()
    additional_fields = set(model.model_dump().keys()) - set(defined_fields)
    return list(additional_fields)


def get_additional_attributes(root: VSSTreeNode, allowed: tuple[str]) -> list[str]:
    if allowed:
        log.info(f"Allowed attributes: {list(allowed)}")
    violations = []
    for node in PreOrderIter(root):
        for field in get_additional_fields(node):
            if field not in allowed:
                violations.append([node.name, field])
    if violations:
        log.info(f"Forbidden additional attributes: {len(violations)}")
    return violations


def remove_delete_nodes(root: VSSTreeNode) -> None:
    size_before = root.size
    delete_nodes = findall(
        root,
        filter_=lambda node: node.data.delete,
    )
    for node in delete_nodes:
        log.debug(f"Deleting node: {node}")
        node.parent = None
    size_after = root.size
    if delete_nodes:
        log.info(
            f"Nodes deleted, marked={len(delete_nodes)}, overall={size_before - size_after}"
        )


def get_root_with_name(roots: list[VSSTreeNode], name: str) -> VSSTreeNode | None:
    for root in roots:
        if root.name == name:
            return root
    return None


def expand_instance(root: VSSTreeNode, instance: str) -> None:
    root_copy = deepcopy(root)
    root.children = []
    for i in expand_string(str(instance)):
        new_child = deepcopy(root_copy)
        new_child.parent = root
        new_child.name = i
        new_child.data.instances = []  # type: ignore


def get_instance_nodes(root: VSSTreeNode) -> tuple[VSSTreeNode, ...]:
    return findall(
        root,
        filter_=lambda node: isinstance(node.data, VSSBranch) and node.data.instances,
    )


def expand_instances(root: VSSTreeNode) -> None:
    instance_nodes = get_instance_nodes(root)
    iterations = 0
    while instance_nodes:
        iterations += 1
        for node in instance_nodes:
            for instance in reversed(node.data.instances):  # type: ignore
                expand_instance(node, instance)
            node.data.instances = []  # type: ignore
        instance_nodes = get_instance_nodes(root)
    log.info(f"Iterations: {iterations}")


def build_trees(data: dict[str, Any]) -> tuple[list[VSSTreeNode], list[VSSTreeNode]]:
    nodes: dict[str, VSSTreeNode] = {}

    for k, v in data.items():
        node = VSSTreeNode(get_name(k), v)
        node.children = []
        parent = get_expected_parent(k)
        if parent and parent in nodes:
            node.parent = nodes[parent]
        else:
            for child_id in find_children_ids(list(nodes.keys()), k):
                node.children.append(nodes[child_id])
        nodes[k] = node

    roots = []
    orphans = []
    for fqn, node in nodes.items():
        if not node.parent:
            if SEPARATOR not in fqn:
                roots.append(node)
            else:
                orphans.append(node)

    if not roots:
        raise NoRootsException()

    if orphans:
        log.warning(f"Orphans: {len(orphans)}")
    for root in roots:
        remove_delete_nodes(root)
        log.info(f"Tree, root='{root.name}', size={root.size}, height={root.height}")
    return roots, orphans


def expand_string(s: str) -> list[str]:
    """
    Expands or unrolls a string that has python syntax array
    definitions inside.

    Example: "abc[1,2]def['A','B']"
    Result:
    - abc1defA
    - abc1defB
    - abc2defA
    - abc2defB

    """
    pattern = r".*(\[.*\]).*"
    match = re.match(pattern, s)
    if not match:
        return [s]

    expanded = []
    list_group = match.group(1)
    try:
        entries = eval(list_group)
    except Exception:
        raise InvalidExpansionEntryException(f"Could not evaluate: '{list_group}'")
    for entry in entries:
        expanded_entry = s.replace(list_group, str(entry))
        if "[" in expanded_entry:
            expanded.extend(expand_string(expanded_entry))
        else:
            expanded.append(expanded_entry)
    return expanded
