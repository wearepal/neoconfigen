# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import sys
from enum import Enum
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
from typing_inspect import is_literal_type  # type: ignore

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

    if is_literal_type(type_):
        type_ = _resolve_literal(type_)

    if hasattr(type_, "__name__"):
        name = str(type_.__name__)
    elif sys.version_info < (3, 7, 0):
        # Python 3.6
        if type_.__origin__ is not None:
            name = type_str(type_.__origin__)
        else:
            name = str(type_)
            if name.startswith("typing."):
                name = name[len("typing.") :]

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
    else:
        args_str = ", ".join(type_str(inner_type) for inner_type in (list(args)))
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
        origin = getattr(import_, "__origin__", None)
        if import_ is Any:
            classname = "Any"
        elif import_ is Optional:  # type: ignore
            classname = "Optional"
        elif origin is Union:  # type: ignore
            classname = "Union"
        elif origin is list:
            classname = "List"
        elif origin is tuple:
            classname = "Tuple"
        elif origin is dict:
            classname = "Dict"
        else:
            classname = import_.__name__
        if not is_primitive_type_annotation(import_) or issubclass(import_, Enum):
            tmp.add(f"from {import_.__module__} import {classname}")

    return sorted(list(tmp.union(string_imports)))


def collect_imports(imports: Set[Type], type_: Type) -> None:
    # Literal values are not types, necessitating this special-casing, inelegant as it is.
    if not is_literal_type(type_):
        for arg in get_args(type_):
            if arg is not ...:
                collect_imports(imports, arg)
        if _resolve_optional(type_)[0] and type_ is not Any:
            type_ = Optional
        imports.add(type_)
