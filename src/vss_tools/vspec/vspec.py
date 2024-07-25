from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from vss_tools import log


class IncludeStatementException(Exception):
    pass


class IncludeNotFoundException(Exception):
    pass


class InvalidSpecDuplicatedEntryException(Exception):
    pass


class SpecException(Exception):
    pass


class Include:
    def __init__(self, statement: str, prefix: str | None = None):
        self.statement = statement
        split = statement.split()
        if len(split) < 2:
            raise IncludeStatementException(f"Malformed include statement: {statement}")
        self.target = split[1]
        self.prefix = prefix
        if len(split) == 3:
            if self.prefix is not None:
                self.prefix += f".{split[2]}"
            else:
                self.prefix = split[2]

    def resolve_path(self, include_dirs: list[Path]) -> Path:
        for dir in include_dirs:
            path = dir / self.target
            if path.exists():
                return path
        raise IncludeNotFoundException(
            f"Unable to find include {self.target}. Include dirs: {include_dirs}"
        )


def strict_dict_update(base: dict[str, Any], update: dict[str, Any]) -> None:
    for k, v in update.items():
        if k in base:
            log.warning(f"Spec Conflict.\nCurrent content: {base[k]}")
            log.warning(f"Requested content: {v}")
            raise InvalidSpecDuplicatedEntryException(f"Duplicated key: {k}")
        base[k] = v


def deep_update(base: dict[str, Any], update: dict[str, Any]) -> None:
    for key, value in update.items():
        if isinstance(value, dict):
            if key in base and isinstance(base[key], dict):
                deep_update(base[key], value)
            else:
                base[key] = copy.deepcopy(value)
        else:
            base[key] = value


class VSpec:
    def __init__(
        self, source: Path, include_dirs: list[Path], prefix: str | None = None
    ):
        self.source = source
        self.prefix = prefix
        self.include_dirs = [source.parent] + include_dirs
        self.include_dirs = list(set(self.include_dirs))
        log.debug(f"Include dirs: {include_dirs}")

        self.content = source.read_text()

        self.data = yaml.safe_load(self.content)
        if prefix:
            tmp_data = {}
            for k, v in self.data.items():
                new_key = f"{prefix}.{k}"
                tmp_data[new_key] = v
            self.data = tmp_data

        lines = self.content.splitlines()
        include_statements = [
            line.strip() for line in lines if line.strip().startswith("#include")
        ]
        includes = [Include(statement, prefix) for statement in include_statements]
        for include in includes:
            s = VSpec(
                include.resolve_path(self.include_dirs), include_dirs, include.prefix
            )
            strict_dict_update(self.data, s.data)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}, src={self.source}, prefix={self.prefix}"

    def update(self, other: VSpec) -> None:
        deep_update(self.data, other.data)


def load_vspec(include_dirs: tuple[Path], specs: list[Path]) -> VSpec:
    spec = None
    for s in specs:
        includes = list(include_dirs) + [s.parent]
        log.info(f"Loading vspec: {s}")
        vs = VSpec(s, list(includes))
        if spec:
            spec.update(vs)
        else:
            spec = vs
    if not spec:
        msg = f"Weird behavior. Could not load any spec: {specs}"
        log.error(msg)
        raise SpecException(msg)
    return spec
