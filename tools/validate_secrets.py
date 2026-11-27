#!/usr/bin/env python3
"""Validate Rahti credential byte consistency without printing secrets."""
from __future__ import annotations

import argparse
from pathlib import Path


def read_password(path: Path) -> bytes:
    value = path.read_bytes()
    if not value or b"\n" in value or b"\r" in value:
        raise ValueError(f"{path.name} must be non-empty and newline-free")
    try:
        value.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError(f"{path.name} must contain ASCII bytes") from error
    return value


def validate(directory: Path) -> None:
    mqtt_password = read_password(directory / "mqtt-password")
    read_password(directory / "postgres-password")
    broker_entry = (directory / "password_file").read_bytes()
    prefix = b"roadsense-remote:"
    if not broker_entry.startswith(prefix) or not broker_entry.endswith(b"\n"):
        raise ValueError("password_file must contain the expected broker username")
    hashed_value = broker_entry[len(prefix) : -1]
    if not hashed_value.startswith(b"$7$") or mqtt_password in broker_entry:
        raise ValueError("password_file must contain a Mosquitto hash, not plaintext")
    for name in ("ca.crt", "server.crt", "server.key"):
        if not (directory / name).is_file() or not (directory / name).stat().st_size:
            raise ValueError(f"missing private file: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    validate(args.directory)
    print("Credential files are byte-consistent; values were not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
