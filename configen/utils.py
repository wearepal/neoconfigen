# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import sys
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
)

from typing_extensions import TypeAlias
from typing_inspect import is_literal_type, is_union_type  # type: ignore

from omegaconf._utils import _resolve_optional, is_primitive_type_annotation

PrimitiveType: TypeAlias = Union[
    Type[int], Type[bool], Type[str], Type[bytes], Type[Enum], Type[None]
]


def _resolve_literal(
    type_: Literal,
) -> Union[PrimitiveType, Type[PrimitiveType]]:
    values = get_args(type_)
    assert values
    value_types = set(type(value) for value in values)
    if len(value_types) == 1:
        return value_types.pop()
    # Constructing a Union type dynamically using a tuple is perfectly valid.
    return Union[tuple(value_types)]  # type: ignore


# borrowed from OmegaConf
def type_str(type_: Any) -> str:
    is_optional, type_ = _resolve_optional(type_)
    if type_ is None:
        return type(type_).__name__
    if type_ is Any:
        return "Any"
    if type_ is ...:
        return "..."

    if is_literal_type(type_) or get_origin(type_) is Literal:
        type_ = _resolve_literal(type_)

    if hasattr(type_, "__name__"):
        name = str(type_.__name__)
    elif type_._name is None and (get_origin(type_) is not None):
        name = type_str(type_.__origin__)
    else:
        name = str(type_._name)

    args = get_args(type_) if hasattr(type_, "__args__") else None
    if args is None:
        ret = name
    elif name == "Callable":
        in_args_str = ", ".join(type_str(inner_type) for inner_type in args[0])
        out_args_str = type_str(args[1])
        ret = f"{name}[[{in_args_str}], {out_args_str}]"
    elif name == "Union":
        args_str = ", ".join(sorted(type_str(inner_type) for inner_type in args))
        ret = f"{name}[{args_str}]"
    else:
        args_str = ", ".join(type_str(inner_type) for inner_type in args)
        ret = f"{name}[{args_str}]"
    if is_optional:
        return f"Optional[{ret}]"
    else:
        return ret


def is_tuple_annotation(type_: Any) -> bool:
    origin = getattr(type_, "__origin__", None)
    if sys.version_info < (3, 7, 0):
        return origin is Tuple or type_ is Tuple  # pragma: no cover
    else:
        return origin is tuple  # pragma: no cover


def convert_imports(imports: Set[Type], string_imports: Set[str]) -> List[str]:
    tmp = set()
    for import_ in imports:
        if import_ is Any:
            classname = "Any"
        elif import_ is Optional:  # type: ignore
            classname = "Optional"
        elif import_ is Union:  # type: ignore
            classname = "Union"
        else:
            origin = getattr(import_, "__origin__", None)
            if origin is list:
                classname = "List"
            elif origin is tuple:
                classname = "Tuple"
            elif origin is dict:
                classname = "Dict"
            else:
                classname = import_.__name__
        if (
            not is_primitive_type_annotation(import_)
            or issubclass(import_, Enum)
            or (import_ is Path)
        ):
            if import_.__module__ != "builtins":
                tmp.add(f"from {import_.__module__} import {classname}")

    return sorted(list(tmp.union(string_imports)))


def collect_imports(imports: Set[Type], type_: Type) -> None:
    # Literal values are not types, necessitating this special-casing, inelegant as it is.
    if not is_literal_type(type_) and get_origin(type_) is not Literal:
        for arg in get_args(type_):
            if arg is not ...:
                collect_imports(imports, arg)
        imports_ = set()
        is_opt, inner_type = _resolve_optional(type_)
        if is_opt and type_ is not Any:
            imports_.add(Optional)
            if is_union_type(inner_type):
                imports_.add(Union)
        elif is_union_type(type_):
            imports_.add(Union)
        else:
            imports_.add(type_)
        imports.update(imports_)
