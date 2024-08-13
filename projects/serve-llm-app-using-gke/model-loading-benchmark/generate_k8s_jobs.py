#!/usr/bin/python3
# Copyright 2024 Google LLC
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

"""Generate Job manifests for testcases."""

import argparse
import os.path
import sys
import types
from typing import Any

from yamlpath import Processor
from yamlpath import YAMLPath
from yamlpath.common import Parsers
from yamlpath.wrappers import ConsolePrinter
from yamlpath.merger import Merger, MergerConfig


CONTAINER_BASE_PATH = "spec.template.spec.containers[name=inference-server]"

logging_args = types.SimpleNamespace(quiet=False, verbose=True, debug=False)
logger = ConsolePrinter(logging_args)
yaml = Parsers.get_yaml_editor()
yaml.indent(mapping=2, sequence=2, offset=0)


def process_model(data, model):
    """Replace model."""
    processor = Processor(logger, data)
    model_path = YAMLPath(CONTAINER_BASE_PATH + ".env[name=MODEL_ID].value")
    processor.set_value(model_path, model)


def reorder_right(data):
    """Put **.name to the first of ordered dict."""
    processor = Processor(logger, data)
    for n in processor.get_nodes(YAMLPath("**.name")):
        n.parent.move_to_end("name", False)


def generate_manifest(yaml_data: Any,
                      overlay_data: Any,
                      casefile: str,
                      opts: argparse.Namespace):
    """Merge yaml together to generate test manifests."""

    merger_config = MergerConfig(logger,
                                 types.SimpleNamespace(aoh="deep"),
                                 rules={},
                                 keys={"**.name":"name"})
    merger = Merger(logger, yaml_data, merger_config)

    reorder_right(overlay_data)
    merger.merge_with(overlay_data)

    merger.prepare_for_dump(yaml, "stdout")

    if opts.model:
        process_model(merger.data, opts.model)

    output_filename = f"run-{opts.prefix}{os.path.basename(casefile)}"
    with open(output_filename,
              "w",
              encoding="utf-8") as of:
        logger.info(f"Creating file: {output_filename}")
        yaml.dump(merger.data, of)


def main(opts):
    """Merge yamls given in commandline to generate test job manifests."""

    inputfile = opts.input_file
    cases = opts.overlay
    for casefile in cases:
        yaml_data, doc_loaded = Parsers.get_yaml_data(yaml, logger, inputfile)
        if not doc_loaded:
            sys.exit(1)
        overlay_data, doc_loaded = Parsers.get_yaml_data(yaml, logger, casefile)
        if not doc_loaded:
            sys.exit(1)
        generate_manifest(yaml_data, overlay_data, casefile, opts)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Job manifests for testcases."
    )
    parser.add_argument(
        "-p",
        "--output-prefix",
        dest="prefix",
        default="",
        type=str,
        help="Output filename prefix.",
    )
    parser.add_argument(
        "-m", "--model",
        dest="model", help="The models to be tested"
    )
    parser.add_argument("-n", "--nodepool",
                        help="Run the jobs in this nodepool")
    parser.add_argument(
        "--skip-case",
        dest="skipped_cases",
        default=[],
        action="append",
        help="This one or mode cases: huggingface gcsfuse pvc",
    )
    parser.add_argument("-i",
                        "--input", dest="input_file",
                        type=str, help="The base Job definition.")
    parser.add_argument("overlay", type=str,
                        nargs="+",
                        action="extend",
                        help="The case overlay file.")

    args = parser.parse_args()
    main(args)
