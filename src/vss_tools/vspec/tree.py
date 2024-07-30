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


class MultipleRootsException(Exception):
    pass


class InvalidExpansionEntryException(Exception):
    pass


class VSSNode(Node):  # type: ignore[misc]
    separator = SEPARATOR

    def __init__(self, name: str, data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
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

    def get_node_with_fqn(self, fqn: str, sep: str = SEPARATOR) -> VSSNode | None:
        results = findall(self, filter_=lambda n: n.get_fqn(sep) == fqn)
        if results:
            return results[0]
        return None

    def connect(self, fqn: str, node: VSSNode) -> VSSNode | None:
        if self.get_node_with_fqn(fqn):
            log.info(f"Already connected: {fqn}")
            return None
        target_fqn = get_expected_parent(fqn)
        if not target_fqn:
            return None
        target = self.get_node_with_fqn(target_fqn)
        if target:
            node.parent = target
            return target
        else:
            auto_node = VSSNode(
                get_name(target_fqn),
                {"type": "branch", "description": "Auto generated"},
            )
            node.parent = auto_node
            return self.connect(target_fqn, auto_node)

    def expand_instances(self) -> None:
        instance_nodes = self.get_instance_nodes()
        iterations = 0
        while instance_nodes:
            iterations += 1
            for i, node in enumerate(instance_nodes):
                # We make a copy of the current node
                # since we need it as a template for instances
                ref_node = deepcopy(node)
                ref_node.children = []

                # We only want to add children to the template
                # that are marked as instantiate=True
                for c in node.children:
                    if c.data.instantiate:
                        c.parent = ref_node

                # A dynamic list with points where new instances
                # should be attached to
                roots = [node]

                # Harmonizing instances attribute to be a list
                instances = getattr(node.data, "instances", [])
                if isinstance(instances, str):
                    instances = [instances]

                for instance in instances:
                    roots = expand_instance(roots, ref_node, instance)

                # Instances have been expanded, therefore remove them
                # to not cause a recursion
                node.data.instances = []  # type: ignore

                # We replace nodes in the expanded instance tree
                # that have been defined to be overwritten in the vspec
                # or an overlay
                replaced = []
                for c in ref_node.children:
                    match = findall(node, filter_=lambda n: n.get_fqn() == c.get_fqn())
                    if match:
                        replaced.append(c)
                        match[0].data = c.data
                        match[0].children += c.children

                # The rest of the initial node children can be added
                # to the current roots
                add = tuple(
                    filter(
                        lambda x: x.get_fqn() not in [r.get_fqn() for r in replaced],
                        ref_node.children,
                    )
                )
                log.debug(f"Adding to leafs: {add}")

                # If we are at the last iteration we need to set the root
                # points to the leafs of our tree in order to attach
                # initially copied node childen correctly
                if i == len(instance_nodes) - 1:
                    roots = findall(node, filter_=lambda n: n.is_leaf)

                for root in roots:
                    # for root in findall(node, filter_=lambda n: n.is_leaf):
                    for a in deepcopy(add):
                        # We can attach the node to the root point
                        # unless it is already there (explicitly) set
                        # in a vspec
                        if not findall(root, filter_=lambda n: n.name == a.name):
                            a.parent = root

            instance_nodes = self.get_instance_nodes()
        if iterations > 0:
            log.info(f"Instance expansion, iterations={iterations}")

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


def build_tree(
    data: dict[str, Any], connect_orphans: bool = False
) -> tuple[VSSNode, dict[str, VSSNode]]:
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
    orphans = {}
    for fqn, node in nodes.items():
        if not node.parent:
            if SEPARATOR not in fqn:
                roots.append(node)
            else:
                orphans[fqn] = node

    if not roots:
        raise NoRootsException()

    if len(roots) > 1:
        raise MultipleRootsException(f"{[r.name for r in roots]}")

    root: VSSNode = roots[0]
    if connect_orphans:
        connected_fqns = []
        for fqn, orphan in orphans.items():
            connected = root.connect(fqn, orphan)
            if connected:
                connected_fqns.append(fqn)
        for fqn in connected_fqns:
            del orphans[fqn]

    if orphans:
        log.warning(f"Orphans: {len(orphans)}")

    log.info(f"Tree, root='{root.name}', size={
            root.size}, height={root.height}")
    return root, orphans


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
