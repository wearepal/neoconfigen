# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import sys
from enum import Enum
from typing import Any, List, Optional, Set, Tuple, Type
from typing_inspect import get_args, get_origin

from omegaconf._utils import _resolve_optional, is_primitive_type


# borrowed from OmegaConf
def type_str(type_: Any) -> str:
    is_optional, type_ = _resolve_optional(type_)
    if type_ is None:
        return type(type_).__name__
    if type_ is Any:
        return "Any"
    if type_ is ...:
        return "..."

    if sys.version_info < (3, 7, 0):  # pragma: no cover
        # Python 3.6
        if hasattr(type_, "__name__"):
            name = str(type_.__name__)
        else:
            if type_.__origin__ is not None:
                name = type_str(type_.__origin__)
            else:
                name = str(type_)
                if name.startswith("typing."):
                    name = name[len("typing.") :]
    else:  # pragma: no cover
        # Python >= 3.7
        if hasattr(type_, "__name__"):
            name = str(type_.__name__)
        else:
            if type_._name is None:
                if get_origin(type_) is not None:
                    name = type_str(type_.__origin__)
            else:
                name = str(type_._name)

    args = get_args(type_) if hasattr(type_, "__args__") else None
    # Callable needs to be special-cased: its args come in the form of a
    # tuple and the string needs to be formatted such that the first argument
    # is a list of input types (which need to be joined with ','s, as for lists
    # and tuples) and the second argument is the return type.
    if name == "Callable":
        in_args_str = ", ".join([type_str(inner_type) for inner_type in args[0]])
        out_args_str = type_str(args[1])
        ret = f"{name}[[{in_args_str}], {out_args_str}]"
    elif args is not None:
        args_str = ", ".join([type_str(inner_type) for inner_type in (list(args))])
        ret = f"{name}[{args_str}]"
    else:
        ret = name
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
        elif import_ is Optional:
            classname = "Optional"
        else:
            if origin is list:
                classname = "List"
            elif origin is tuple:
                classname = "Tuple"
            elif origin is dict:
                classname = "Dict"
            else:
                classname = import_.__name__
        if not is_primitive_type(import_) or issubclass(import_, Enum):
            tmp.add(f"from {import_.__module__} import {classname}")

    return sorted(list(tmp.union(string_imports)))


def collect_imports(imports: Set[Type], type_: Type) -> None:
    for arg in get_args(type_):
        if arg is not ...:
            collect_imports(imports, arg)
    if _resolve_optional(type_)[0] and type_ is not Any:
        type_ = Optional
    imports.add(type_)
