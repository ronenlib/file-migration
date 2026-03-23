from __future__ import annotations

import argparse
import logging

from file_migration.composition import CompositionRoot
from file_migration.config.loader import JobConfigLoader
from file_migration.logging_utils import configure_logging

LOGGER = logging.getLogger(__name__)


class CliApp:
    def run(self) -> None:
        configure_logging()
        args = self._parse_args()
        LOGGER.info("loading config from %s", args.config_path)
        config = JobConfigLoader().load(args.config_path)
        composition = CompositionRoot(config)

        if args.command == "export":
            LOGGER.info("starting export command for job=%s", config.job_name)
            composition.build_export_migration().run()
            return

        if args.command == "delete":
            LOGGER.info("starting delete command for job=%s", config.job_name)
            composition.build_delete_migration().run()
            return

        raise ValueError(f"Unsupported command: {args.command}")

    def _parse_args(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(prog="file-migration")
        subparsers = parser.add_subparsers(dest="command", required=True)

        export_parser = subparsers.add_parser(
            "export", help="Export source files into target storage"
        )
        export_parser.add_argument("config_path", type=str)

        delete_parser = subparsers.add_parser("delete", help="Delete exported files from source")
        delete_parser.add_argument("config_path", type=str)

        return parser.parse_args()


def main() -> None:
    CliApp().run()


if __name__ == "__main__":
    main()
