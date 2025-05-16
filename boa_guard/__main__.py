import argparse
import importlib
from pathlib import Path

_COMMAND_MAP = {
    "bundles": ("boa_guard.bundles", "Generate FHIR bundles"),
    "transactions": ("boa_guard.transactions", "Create FHIR transactions"),
    "push": ("boa_guard.push", "POST to server"),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="boa-guard",
        description="Transform BOA results into the corresponding FHIR profiles.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
            "-i",
            "--input",
            type=Path,
            required=True,
            help="Path to the BOA folder",
        )
        subparser.add_argument(
            "-o",
            "--output",
            type=Path,
            required=True,
            help="Path to the Output folder",
        )

    for name, (_, help) in _COMMAND_MAP.items():
        add_common(sub.add_parser(name, help=help))
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    if not args.input.is_dir():
        raise NotADirectoryError(f"Folder '{args.input.resolve()}' doesn't exist.")

    module = importlib.import_module(_COMMAND_MAP[args.command][0])
    module.main(args.input, args.output)


if __name__ == "__main__":
    main()
