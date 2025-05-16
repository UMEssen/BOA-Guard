from pathlib import Path
from typing import Iterator, TypeAlias

StrPath: TypeAlias = str | Path


def iterator(path: Path) -> Iterator[Path]:
    for output_file in path.rglob("*.xlsx"):
        yield output_file.parent
