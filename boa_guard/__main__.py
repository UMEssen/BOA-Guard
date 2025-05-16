import argparse
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, cast

_COMMAND_MAP = {
    "bundles": ("boa_guard.bundles:main", "Generate FHIR bundles"),
    "tx": ("boa_guard.tx:main", "Create FHIR transactions"),
    "push": ("boa_guard.push:main", "POST to server"),
}


def _resolve_callable(dotted: str) -> Callable[..., Any]:
    module_path, func_name = dotted.split(":")
    module = import_module(module_path)
    return cast(Callable[..., Any], getattr(module, func_name))


def _existing_dir(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"'{path}' is not an existing directory")
    return path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="boa-guard",
        description="Transform BOA results into the corresponding FHIR profiles.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, (target, help_text) in _COMMAND_MAP.items():
        sp = subparsers.add_parser(name, help=help_text)
        sp.add_argument(
            "-f",
            "--fhir-folder",
            type=_existing_dir,
            required=True,
            help="Path to the FHIR bundles / transactions folder",
        )
        if name == "bundles":
            sp.add_argument(
                "-b",
                "--boa-folder",
                type=_existing_dir,
                required=True,
                help="Path to the BOA folder",
            )
        sp.set_defaults(func=_resolve_callable(target))
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    func = args.func
    delattr(args, "func")
    delattr(args, "command")
    func(**vars(args))


if __name__ == "__main__":
    main()
