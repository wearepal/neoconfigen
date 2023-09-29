# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from typing_extensions import TypeAlias

from omegaconf import MISSING, DictConfig


class Color(Enum):
    RED = 0
    GREEN = 1
    BLUE = 2


@dataclass
class User:
    name: str = MISSING
    age: int = MISSING


class LibraryClass:
    """
    Some class from a user library that is incompatible with OmegaConf config
    """

    def __init__(self):
        pass

    def __eq__(self, other):
        return isinstance(other, type(self))


class Empty:
    def __init__(self):
        ...

    def __eq__(self, other):
        return isinstance(other, type(self))


class UntypedArg:
    def __init__(self, param):
        self.param = param

    def __eq__(self, other):
        return isinstance(other, type(self)) and other.param == self.param


class IntArg:
    def __init__(self, param: int):
        self.param = param

    def __eq__(self, other):
        return isinstance(other, type(self)) and other.param == self.param


class PathArg:
    def __init__(self, param: Path):
        self.param = param

    def __eq__(self, other):
        return isinstance(other, type(self)) and other.param == self.param


class Args:
    def __init__(self, *args: Any):
        self.param = args


class Kwargs:
    def __init__(self, **kwargs: Any):
        self.param = kwargs

    def __eq__(self, other):
        return isinstance(other, type(self)) and other.param == self.param


class UnionArg:
    # Union is now supported by OmegaConf for primitive types.
    def __init__(
        self,
        param: Union[int, float],
        param2: Optional[Union[str, Color, bool]] = None,
        param3: Union[str, Path] = "",
        param4: Union[str, DictConfig] = "",
        param5: Union[str, List[str], Tuple[str, ...]] = ("foo", "bar"),
        param6: Union[str, list[str], tuple[str, ...]] = ("foo", "bar"),
    ):
        self.param = param
        self.param2 = param2
        self.param3 = param3
        self.param4 = param4
        self.param5 = param5
        self.param6 = param6

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and other.param == self.param
            and other.param2 == self.param2
            and other.param3 == self.param3
            and other.param4 == self.param4
            and other.param5 == self.param5
            and other.param6 == self.param6
        )


class WithLibraryClassArg:
    def __init__(self, num: int, param: LibraryClass):
        self.num = num
        self.param = param

    def __eq__(self, other):
        return isinstance(other, type(self)) and other.num == self.num and other.param == self.param


@dataclass
class IncompatibleDataclass:
    library: LibraryClass = field(default_factory=LibraryClass)

    def __eq__(self, other):
        return isinstance(other, type(self)) and other.library == self.library


class IncompatibleDataclassArg:
    def __init__(self, num: int, incompat: IncompatibleDataclass):
        self.num = num
        self.incompat = incompat

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and self.num == other.num
            and self.incompat == other.incompat
        )


class WithStringDefault:
    def __init__(
        self,
        no_default: str,
        default_str: str = "Bond, James Bond",
        none_str: Optional[str] = None,
    ):
        self.no_default = no_default
        self.default_str = default_str
        self.none_str = none_str

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and self.no_default == other.no_default
            and self.default_str == other.default_str
            and self.none_str == other.none_str
        )


class WithUntypedStringDefault:
    def __init__(
        self,
        default_str="Bond, James Bond",
    ):
        self.default_str = default_str

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.default_str == other.default_str


class ListValues:
    def __init__(
        self,
        lst: List[str],
        lst2: list[str],
        enum_lst: List[Color],
        passthrough_list: List[LibraryClass],
        dataclass_val: List[User],
        def_value: List[str] = [],
        def_value2: list[str] = [],
    ):
        self.lst = lst
        self.lst2 = lst2
        self.enum_lst = enum_lst
        self.passthrough_list = passthrough_list
        self.dataclass_val = dataclass_val
        self.def_value = def_value
        self.def_value2 = def_value2

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and self.lst == other.lst
            and self.lst2 == other.lst2
            and self.enum_lst == other.enum_lst
            and self.passthrough_list == other.passthrough_list
            and self.dataclass_val == other.dataclass_val
            and self.def_value == other.def_value
            and self.def_value2 == other.def_value2
        )


class DictValues:
    def __init__(
        self,
        dct: Dict[str, str],
        dct2: dict[str, str],
        enum_key: Dict[Color, str],
        dataclass_val: Dict[str, User],
        passthrough_dict: Dict[str, LibraryClass],
        def_value: Dict[str, str] = {},
        def_value2: dict[str, str] = {},
    ):
        self.dct = dct
        self.dct2 = dct2
        self.enum_key = enum_key
        self.dataclass_val = dataclass_val
        self.passthrough_dict = passthrough_dict
        self.def_value = def_value
        self.def_value2 = def_value2

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and self.dct == other.dct
            and self.dct2 == other.dct2
            and self.enum_key == other.enum_key
            and self.dataclass_val == other.dataclass_val
            and self.passthrough_dict == other.passthrough_dict
            and self.def_value == other.def_value
            and self.def_value2 == other.def_value2
        )


class PeskySentinel(object):
    def __repr__(self):
        return "<I am a pesky sentinel>"


pesky = PeskySentinel()


class PeskySentinelUsage:
    def __init__(self, foo=pesky):
        self.foo = foo

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.foo == other.foo


class Tuples:
    def __init__(
        self,
        t1: Tuple[float, float],
        t2: tuple[float, float],
        t3=(1, 2, 3),
        t4: Tuple[float, ...] = (0.1, 0.2, 0.3),
    ):
        self.t1 = t1
        self.t2 = t2
        self.t3 = t3
        self.t4 = t4

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and self.t1 == other.t1
            and self.t2 == other.t2
            and self.t3 == other.t3
            and self.t4 == other.t4
        )


_LITERAL_WARN: TypeAlias = Literal["warn"]


class WithLiterals:
    def __init__(
        self,
        activation: Literal["relu", "gelu"],
        fairness: Optional[Literal["DP", "EO"]] = None,
        bit_depth: Optional[Union[Literal[5, 8], float]] = 5,
        color1: Literal[Color.BLUE, Color.GREEN] = Color.BLUE,
        color2: Optional[Literal[Color.BLUE, Color.GREEN]] = Color.GREEN,
        deterministic: Optional[Union[bool, _LITERAL_WARN]] = None,
        mixed_type_lit: Literal[0, "foo", "bar", Color.BLUE] = 0,
        unioned_mixed_type_lit: Union[Literal["foo", "bar", Color.BLUE], int] = 47,
    ):
        self.activation = activation
        self.fairness = fairness
        self.bit_depth = bit_depth
        self.color1 = color1
        self.color2 = color2
        self.deterministic = deterministic
        self.mixed_type_lit = mixed_type_lit
        self.unioned_mixed_type_lit = unioned_mixed_type_lit

    def __eq__(self, other):
        return (
            isinstance(other, type(self))
            and self.activation == other.activation
            and self.fairness == other.fairness
            and self.bit_depth == other.bit_depth
            and self.color1 == other.color1
            and self.color2 == other.color2
            and self.deterministic == other.deterministic
            and self.mixed_type_lit == other.mixed_type_lit
            and self.unioned_mixed_type_lit == other.unioned_mixed_type_lit
        )
