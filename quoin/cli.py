from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from . import blocks as block_commands
from .assemble import build
from .check import check, doctor
from .errors import QuoinError
from .fetch import run as fetch
from .scaffold import init


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="quoin")
    sub = command.add_subparsers(dest="command", required=True)
    init_parser = sub.add_parser("init", help="scaffold a book directory")
    init_parser.add_argument("directory", type=Path)
    fetch_parser = sub.add_parser("fetch", help="resolve and normalize sources")
    fetch_parser.add_argument("--offline", action="store_true")
    blocks_parser = sub.add_parser("blocks", help="list authored block slots")
    blocks_parser.add_argument("--missing", action="store_true")
    blocks_parser.add_argument("--json", action="store_true")
    build_parser = sub.add_parser("build", help="assemble an EPUB3 file")
    build_parser.add_argument("--draft", action="store_true")
    build_parser.add_argument("--profile", choices=["default", "kepub"], default="default")
    check_parser = sub.add_parser("check", help="check the built EPUB")
    check_parser.add_argument("--release", action="store_true")
    check_parser.add_argument("--profile", choices=["default", "kepub"], default="default")
    sub.add_parser("doctor", help="check required tools")
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path.cwd().resolve()
    try:
        if args.command == "init":
            init(args.directory.resolve())
            print(f"initialized {args.directory.resolve()}")
        elif args.command == "fetch":
            records = fetch(root, args.offline)
            for source_id, record in records.items():
                print(f"{source_id}: {record['word_count']} words, {record['bytes']} bytes")
        elif args.command == "blocks":
            orders = block_commands.work_orders(root, args.missing)
            if args.json:
                print(json.dumps(orders, indent=2, ensure_ascii=False))
            else:
                print("block_id  kind  status")
                for order in orders:
                    print(f"{order['block_id']}  {order['kind']}  {order['status']}")
        elif args.command == "build":
            target, record = build(root, args.draft, args.profile)
            print("stage      wall_ms  cache_hit")
            for name, stage in record["stages"].items():
                print(f"{name:<10} {stage['wall_ms']:>9.3f} {str(stage['cache_hit']).lower():>9}")
            print(target)
        elif args.command == "check":
            passed, payload = check(root, args.release, args.profile)
            print("check          result  detail")
            for name, value in payload["tests"].items():
                print(f"{name:<14} {'PASS' if value['pass'] else 'FAIL':<6} {value['detail']}")
            return 0 if passed else 1
        elif args.command == "doctor":
            passed, values = doctor(root)
            for name, value in values.items():
                print(f"{name}: {value}")
            return 0 if passed else 1
        return 0
    except QuoinError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"quoin {args.command} crashed (bug): {exc}", file=sys.stderr)
        traceback.print_tb(exc.__traceback__, limit=3, file=sys.stderr)
        return 2
