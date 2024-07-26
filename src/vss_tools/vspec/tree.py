from __future__ import annotations
import re
from typing import Any
import uuid

from anytree import Node, PreOrderIter, findall
from copy import deepcopy

from vss_tools import log
from vss_tools.vspec.model import (
    VSSDataDatatype,
    get_model,
    VSSDataBranch,
    VSSDataSensor,
    NodeType,
)
from vss_tools.vspec.datatypes import Datatypes

SEPARATOR = "."


class NoRootsException(Exception):
    pass


class InvalidExpansionEntryException(Exception):
    pass


class VSSNode(Node):  # type: ignore[misc]
    separator = SEPARATOR

    def __init__(self, name: str, data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        log.debug(f"{self.__class__.__name__}, name={name}")
        self.data = get_model(data, name)
        self.uuid: str | None = None

    def get_fqn(self, sep: str = SEPARATOR) -> str:
        return sep.join([n.name for n in self.path])

    def add_uuids(self) -> None:
        VSS_NAMESPACE = "vehicle_signal_specification"
        namespace_uuid = uuid.uuid5(uuid.NAMESPACE_OID, VSS_NAMESPACE)
        node: VSSNode
        for node in PreOrderIter(self):
            node.uuid = uuid.uuid5(namespace_uuid, node.get_fqn()).hex

    def get_instance_nodes(self) -> tuple[VSSNode, ...]:
        return findall(
            self,
            filter_=lambda node: isinstance(node.data, VSSDataBranch)
            and node.data.instances,
        )

    def expand_instances(self) -> None:
        instance_nodes = self.get_instance_nodes()
        iterations = 0
        while instance_nodes:
            iterations += 1
            for node in instance_nodes:
                node_copy = deepcopy(node)
                node.children = []
                for instance in node.data.instances:  # type: ignore
                    expand_instance(node, node_copy, instance)
                node.data.instances = []  # type: ignore
            instance_nodes = self.get_instance_nodes()
        log.info(f"Instance expand iterations: {iterations}")

    def remove_delete_nodes(self) -> None:
        size_before = self.size
        delete_nodes = findall(
            self,
            filter_=lambda node: node.data.delete,
        )
        for node in delete_nodes:
            log.debug(f"Deleting node: {node}")
            node.parent = None
        size_after = self.size
        if delete_nodes:
            log.info(
                f"Nodes deleted, marked={len(delete_nodes)}, overall={size_before - size_after}"
            )

    def get_naming_violations(self) -> list[str]:
        violations = []
        log.info(f"Checking node name compliance for {self.name}")
        camel_case_pattern = re.compile("[A-Z][A-Za-z0-9]*$")
        for node in PreOrderIter(self):
            match = re.match(camel_case_pattern, node.name)
            if not match:
                violations.append([node.name, "not CamelCase"])
            if isinstance(node.data, VSSDataDatatype):
                if node.data.datatype == Datatypes.BOOLEAN[0]:
                    if not node.name.startswith("Is"):
                        violations.append([node.name, "Not starting with 'Is'"])
        if violations:
            log.info(f"Naming violations: {len(violations)}")
        return violations

    def get_additional_attributes(self, allowed: tuple[str]) -> list[str]:
        if allowed:
            log.info(f"Allowed attributes: {list(allowed)}")
        violations = []
        for node in PreOrderIter(self):
            for field in node.data.get_additional_fields():
                if field not in allowed:
                    violations.append([node.name, field])
        if violations:
            log.info(f"Forbidden additional attributes: {len(violations)}")
        return violations

    def as_flat_dict(self, with_extra_attributes: bool) -> dict[str, Any]:
        data = {}
        for node in PreOrderIter(self):
            key = node.get_fqn()
            data[key] = node.data.as_dict(with_extra_attributes)
            if node.uuid:
                data[key]["uuid"] = node.uuid
        return data

    @staticmethod
    def merge_attributes(node: VSSNode, other_node: VSSNode) -> None:
        for key, value in other_node.data.as_dict().items():
            if key == "type":
                setattr(node.data, key, NodeType(value))
            else:
                setattr(node.data, key, value)

    def merge(self, other: VSSNode) -> None:

        fqns = [node.get_fqn() for node in PreOrderIter(self)]

        for other_node in PreOrderIter(other):
            if "autogenerated" in other_node.data.get_additional_fields():
                log.debug(f"Skipping autogenerated node '{other_node.name}'")
                continue

            other_fqn = other_node.get_fqn()
            if other_fqn in fqns:
                log.info(f"Overwriting node '{other_fqn}'")
                for node in PreOrderIter(self):
                    if node.get_fqn() == other_fqn:
                        self.merge_attributes(node, other_node)
            else:
                log.info(f"Adding node '{other_node.get_fqn()}' from overlay.")
                for node in PreOrderIter(self):
                    if node.get_fqn() == get_expected_parent(other_node.get_fqn()):
                        other_node.parent = node


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


def get_root_with_name(roots: list[VSSNode], name: str) -> VSSNode | None:
    for root in roots:
        if root.name == name:
            return root
    return None


def expand_instance(root: VSSNode, root_copy: VSSNode, instance: str) -> None:
    for i in expand_string(str(instance)):
        new_child = deepcopy(root_copy)
        new_child.parent = root
        new_child.name = i
        new_child.data.instances = []  # type: ignore


def build_trees(
    data: dict[str, Any], is_overlay: bool = False
) -> tuple[list[VSSNode], list[VSSNode]]:
    nodes: dict[str, VSSNode] = {}

    for k, v in data.items():
        node = VSSNode(get_name(k), v)
        node.children = []
        parent = get_expected_parent(k)
        if parent and parent in nodes and not is_overlay:
            node.parent = nodes[parent]
        elif parent and parent in nodes and is_overlay:
            node.parent = nodes[parent]
            # ToDo do we have to do anything here? Is this elif needed?
        elif parent and parent not in nodes and is_overlay:
            log.warning(
                f"Parent of '{k}' not found, so automatically creating to build overlay tree."
            )
            node.parent = autocreate_branches(nodes, parent)
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
        root.remove_delete_nodes()
        log.info(f"Tree, root='{root.name}', size={root.size}, height={root.height}")
    return roots, orphans


def autocreate_branches(nodes: dict[str, VSSNode], parent_path: str) -> VSSNode:
    log.info(f"Implicitly creating branch '{parent_path}'")
    parent = VSSNode(
        get_name(parent_path),
        {
            "type": "branch",
            "description": "Autogenerated branch",
            "autogenerated": True,
        },
    )
    nodes[parent_path] = parent
    parent_of_parent = get_expected_parent(parent_path)
    if parent_of_parent and parent_of_parent not in nodes:
        parent.parent = autocreate_branches(nodes, parent_of_parent)

    return parent


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
