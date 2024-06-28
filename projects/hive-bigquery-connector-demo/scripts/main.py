# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This script prepares the data for the Hive-BigQuery-Connector demo.

Run this script after the `terraform apply` command, to prepare the data for
the demo.
"""

import argparse
import logging
import sys

import bq_funcs
from logging_funcs import setup_logging
import notebook_funcs
from state import ScriptState

logger = logging.getLogger("main")


def get_parser():
    """Get the command line parser."""
    parser = argparse.ArgumentParser(
        prog="HiveBQConnectorDemoPrep",
        description=(
            "Script to prepare data for the Hive-BigQuery-Connector demo"
        ),
    )
    parser.add_argument(
        "--skip-tables-prep",
        action=argparse.BooleanOptionalAction,
        dest="skip_tables",
        help="Skip (or not) the BigQuery tables preparation step (takes a long "
        "time)",
    )
    parser.set_defaults(skip_tables=False)
    return parser


def run():
    """Main entry point for the script."""
    setup_logging()
    parser = get_parser()
    args = parser.parse_args(sys.argv[1:])

    notebook_full_path = notebook_funcs.compile_notebook()
    notebook_funcs.update_notebook(
        notebook_full_path, ScriptState.tf_state().staging_bucket
    )

    if not args.skip_tables:
        logger.info(
            "Preparing BQ tables - grab a coffee, this will take a while"
        )

        existing_tables = ScriptState.bq_client().list_tables(
            ScriptState.dataset()
        )
        for tbl in existing_tables:
            table = ScriptState.bq_client().get_table(tbl)
            ScriptState.bq_client().delete_table(table)

        bq_funcs.handle_distribution_center()
        bq_funcs.handle_events()
        bq_funcs.handle_inventory_items()
        bq_funcs.handle_order_items()
        bq_funcs.handle_orders()
        bq_funcs.handle_products()
        bq_funcs.handle_users()

    logger.info(
        "Finished! Open %snotebooks/GCS/notebook.ipynb in your browser to "
        "continue.",
        ScriptState.tf_state().jupyter_url,
    )


if __name__ == "__main__":
    run()
