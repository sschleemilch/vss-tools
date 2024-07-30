from __future__ import annotations
import re
from typing import Any
import uuid

from anytree import Node, PreOrderIter, findall
from copy import deepcopy

from vss_tools import log
from vss_tools.vspec.model import VSSDataDatatype, get_vss_data, VSSDataBranch
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
        self.data = get_vss_data(data, name)
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
                ref_node = deepcopy(node)

                exclude_children = []
                include_children = []
                for c in node.children:
                    if c.data.instantiate:
                        include_children.append(c)
                    else:
                        exclude_children.append(c)

                node.children = exclude_children
                ref_node.children = deepcopy(include_children)

                roots = [node]

                instances = getattr(node.data, "instances", [])
                if isinstance(instances, str):
                    instances = [instances]

                for instance in instances:
                    roots = expand_instance(roots, ref_node, instance)

                node.data.instances = []  # type: ignore
                for leaf in findall(node, filter_=lambda n: n.is_leaf):
                    leaf.children = deepcopy(ref_node.children)

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
                f"Nodes deleted, marked={len(delete_nodes)}, overall={
                    size_before - size_after}"
            )

    def get_naming_violations(self) -> list[list[str]]:
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
                        violations.append([node.get_fqn(), "Not starting with 'Is'"])
        if violations:
            log.info(f"Naming violations: {len(violations)}")
        return violations

    def get_extra_attributes(self, allowed: tuple[str, ...]) -> list[list[str]]:
        violations = []
        for node in PreOrderIter(self):
            for field in node.data.get_extra_attributes():
                if field not in allowed:
                    violations.append([node.get_fqn(), field])
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


def expand_instance(
    roots: list[VSSNode], ref_node: VSSNode, instance: list[str] | str
) -> list[VSSNode]:
    requested_instances = []
    if isinstance(instance, list):
        requested_instances = instance
    else:
        requested_instances = [instance]

    new_node_names = []
    for i in requested_instances:
        new_node_names.extend(expand_string(str(i)))
    nodes = []
    for i in new_node_names:
        for root in roots:
            node = deepcopy(ref_node)
            node.name = i
            node.data.instances = []  # type: ignore
            node.parent = root
            node.children = []
            nodes.append(node)
    if len(new_node_names) > 1 or isinstance(instance, list):
        return nodes
    else:
        return roots


def build_trees(data: dict[str, Any]) -> tuple[list[VSSNode], list[VSSNode]]:
    nodes: dict[str, VSSNode] = {}

    for k, v in data.items():
        node = VSSNode(get_name(k), v)
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
        root.remove_delete_nodes()
        log.info(f"Tree, root='{root.name}', size={
                 root.size}, height={root.height}")
    return roots, orphans


def expand_string(s: str) -> list[str]:
    """
    Expands or unrolls a string with a range syntax
    definitions inside.

    Example: "abc[1,4]bar"
    Result:
    - abc1bar
    - abc2bar
    - abc3bar
    - abc4bar

    """
    pattern = r".*(\[(\d+),(\d+)\]).*"
    match = re.match(pattern, s)
    if not match:
        return [s]
    expanded = []
    if int(match.group(2)) > int(match.group(3)):
        raise InvalidExpansionEntryException(f"Invalid range: '{match.group(1)}'")
    for i in range(int(match.group(2)), int(match.group(3)) + 1):
        expanded.append(s.replace(match.group(1), str(i)))
    return expanded
