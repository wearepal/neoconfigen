# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import inspect
import logging
import os
import pkgutil
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from textwrap import dedent
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Set,
    Type,
    get_args,
    get_origin,
    get_type_hints,
)

from jinja2 import Environment, PackageLoader, Template  # type: ignore
from typing_inspect import is_callable_type, is_literal_type  # type: ignore

import hydra
from omegaconf import OmegaConf, ValidationError
from omegaconf._utils import (
    _resolve_optional,
    get_dict_key_value_types,
    get_list_element_type,
    is_dict_annotation,
    is_list_annotation,
    is_primitive_type_annotation,
    is_structured_config,
    is_union_annotation,
)

from configen.config import Config, ConfigenConf, ModuleConf
from configen.utils import (
    collect_imports,
    convert_imports,
    is_tuple_annotation,
    type_str,
)

# Adding the current working directory to the PYTHONPATH to allow generation of code
# that is not installed properly
sys.path.append(os.getcwd())

log = logging.getLogger(__name__)

jinja_env = Environment(
    loader=PackageLoader("configen", "templates"),
    keep_trailing_newline=True,
    trim_blocks=True,
)
jinja_env.tests["empty"] = lambda x: x == inspect.Signature.empty


def init_config(conf_dir: str) -> None:
    log.info(f"Initializing config in '{conf_dir}'")

    path = Path(hydra.utils.to_absolute_path(conf_dir))
    path.mkdir(parents=True, exist_ok=True)
    file = path / "configen.yaml"
    if file.exists():
        sys.stderr.write(f"Config file '{file}' already exists\n")
        sys.exit(1)

    sample_config = pkgutil.get_data(__name__, "templates/sample_config.yaml")
    assert sample_config is not None
    file.write_bytes(sample_config)


def save(cfg: ConfigenConf, module: str, code: str) -> None:
    module_path = module.replace(".", "/")

    module_path_pattern = Template(cfg.module_path_pattern).render(module_path=module_path)
    assert module_path_pattern
    path = Path(cfg.output_dir) / module_path_pattern
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code)
    log.info(f"{module}.{module} -> {path}")


@dataclass
class Parameter:
    name: str
    type_str: str
    default: Optional[str]


@dataclass
class ClassInfo:
    module: str
    name: str
    parameters: List[Parameter]
    target: str


def is_incompatible(type_: Type[Any]) -> bool:
    _, type_ = _resolve_optional(type_)
    if type_ in (type(None), tuple, list, dict, Path):
        return False
    try:
        # Literal values must be primitive so no need to run a compatibility-check over them.
        if is_literal_type(type_) or get_origin(type_) is Literal:
            return False
        # Callable isn't a class so the subsequent issubclass check would raise
        # a rype-error if called on it
        elif is_callable_type(type_):
            return True
        elif is_list_annotation(type_):
            lt = get_list_element_type(type_)
            return is_incompatible(lt)
        elif is_dict_annotation(type_):
            kvt = get_dict_key_value_types(type_)
            if not issubclass(kvt[0], (str, Enum)):
                return True
            return is_incompatible(kvt[1])
        elif is_tuple_annotation(type_):
            return any(arg is not ... and is_incompatible(arg) for arg in type_.__args__)  # type: ignore
        elif is_union_annotation(type_):
            args = get_args(type_)
            # OmegaConf only supports the unioning of primitive types; Literal types qualify as
            # 'compatible' here due to downstream conversion into primitive types (since Literal
            # types themselves are currently not supported).
            return any(
                not (
                    is_primitive_type_annotation(arg)
                    or is_literal_type(arg)
                    or get_origin(arg) is Literal
                )
                for arg in args
            )
        origin = get_origin(type_)
        if origin is type:
            args = get_args(type_)
            return bool(is_incompatible(args[0]))  # type: ignore
    except ValidationError:
        return True

    if type_ is Any or issubclass(type_, (int, float, str, bool, Enum)):
        return False
    if is_structured_config(type_):
        try:
            OmegaConf.structured(type_)  # verify it's actually legal
        except ValidationError as e:
            log.debug(
                f"Failed to create DictConfig from ({type_.__name__}) : {e}, flagging as incompatible"
            )
            return True
        return False
    return True


def get_default_flags(module: ModuleConf) -> List[Parameter]:
    def_flags: List[Parameter] = []

    if module.default_flags._convert_ is not None:
        def_flags.append(
            Parameter(
                name="_convert_",
                type_str="str",
                default=f'"{module.default_flags._convert_.name}"',
            )
        )

    if module.default_flags._recursive_ is not None:
        def_flags.append(
            Parameter(
                name="_recursive_",
                type_str="bool",
                default=str(module.default_flags._recursive_),
            )
        )

    return def_flags


def generate_module(cfg: ConfigenConf, module: ModuleConf) -> str:
    classes_map: Dict[str, ClassInfo] = {}
    imports = set()
    string_imports: Set[str] = set()

    default_flags = get_default_flags(module)

    for class_name in module.classes:
        full_name = f"{module.name}.{class_name}"
        cls = hydra.utils.get_class(full_name)
        params: List[Parameter] = []
        params += default_flags
        resolved_hints = get_type_hints(cls.__init__)
        sig = inspect.signature(cls.__init__)

        for name, p in sig.parameters.items():
            # Skip self/args as attributes
            if name == "self" or (
                p.kind
                in (inspect._ParameterKind.VAR_POSITIONAL, inspect._ParameterKind.VAR_KEYWORD)
            ):
                continue
            type_ = type_cached = resolved_hints.get(name, p.annotation)
            default_ = p.default

            missing_value = default_ == sig.empty
            incompatible_value_type = not missing_value and is_incompatible(type(default_))
            missing_annotation_type = name not in resolved_hints
            incompatible_annotation_type = not missing_annotation_type and is_incompatible(type_)

            if isinstance(default_, Enum):
                module_name = getattr(default_, "__module__", None)
                if module_name is not None:  # Import required
                    import_name = default_.__class__.__name__
                    string_imports.add(f"from {module_name} import {import_name}")

            if missing_annotation_type or incompatible_annotation_type:
                type_ = Any
                collect_imports(imports, Any)  # type: ignore

            if not missing_value:
                if type_ == str or type(default_) == str:  # noqa
                    default_ = f'"{default_}"'
                elif isinstance(default_, list):
                    default_ = f"field(default_factory=lambda: {default_})"
                elif isinstance(default_, dict):
                    default_ = f"field(default_factory=lambda: {default_})"

            missing_default = True if incompatible_value_type else missing_value
            collect_imports(imports, type_)  # type: ignore

            if missing_default:
                default_ = "MISSING"
                string_imports.add("from omegaconf import MISSING")

            if isinstance(default_, Enum):
                default_ = Enum.__str__(default_)

            if incompatible_annotation_type:
                default_ = f"{default_}  # {type_str(type_cached)}"
            elif incompatible_value_type:
                default_ = f"{default_}  # {type_str(type(p.default))}"  # if not missing_value:

            params.append(
                Parameter(
                    name=name,
                    type_str=type_str(type_),
                    default=str(default_),
                )
            )
        classes_map[class_name] = ClassInfo(
            target=full_name,
            module=module.name,
            name=class_name,
            parameters=params,
        )

    template = jinja_env.get_template("module.j2")
    rendered = template.render(
        imports=convert_imports(imports, string_imports),
        classes=module.classes,
        classes_map=classes_map,
        header=cfg.header,
    )
    assert isinstance(rendered, str)
    return rendered


@hydra.main(config_path=None, config_name="configen_schema", version_base=None)
def main(cfg: Config):
    if cfg.init_config_dir is not None:
        init_config(cfg.init_config_dir)
        return

    if OmegaConf.is_missing(cfg.configen, "modules"):  # type: ignore
        log.error(
            dedent(
                """\
                Use --config-dir DIR --config-name NAME
                e.g:
                \tconfigen --config-dir conf --config-name configen
                If you have no config dir yet use init_config_dir=DIR to create an initial config dir.
                e.g:
                \tconfigen init_config_dir=conf
                """
            )
        )
        sys.exit(1)

    for module in cfg.configen.modules:
        code = generate_module(cfg=cfg.configen, module=module)
        save(cfg=cfg.configen, module=module.name, code=code)


if __name__ == "__main__":
    main()
