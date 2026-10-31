"""Operator command-line entrypoints for the backend service."""

import argparse
import asyncio

from modest_chic_backend.core.settings import Settings
from modest_chic_backend.modules.auth.bootstrap import bootstrap_owner


def main() -> None:
    """Run the restricted first-owner bootstrap command."""
    parser = argparse.ArgumentParser(prog="modest-chic-backend")
    subparsers = parser.add_subparsers(dest="command", required=True)
    bootstrap_parser = subparsers.add_parser("bootstrap-owner")
    bootstrap_parser.add_argument("--email", required=True)
    arguments = parser.parse_args()
    settings = Settings()
    if arguments.command == "bootstrap-owner":
        owner_id = asyncio.run(bootstrap_owner(email=arguments.email, settings=settings))
        print(f"Invited first owner {owner_id}; no password was seeded.")
