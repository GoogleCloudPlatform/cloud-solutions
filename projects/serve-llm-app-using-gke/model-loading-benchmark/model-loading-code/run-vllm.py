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

"""Mesure vllm startup/model load time."""

# ruff: noqa
import argparse
import os
import time

RUN_NAME = os.getenv("RUN_NAME")

timing = []
timing.append(("START", time.perf_counter()))
# Mesure the time for importing this module.
# pylint:disable-next=unused-import,wrong-import-position
import vllm.entrypoints.api_server

timing.append(("MODULE_IMPORTED", time.perf_counter()))

# pylint:disable-next=wrong-import-position
from vllm.logger import init_logger
# pylint:disable-next=wrong-import-position
from vllm import LLM

logger = init_logger(__name__)


def run_vllm(model: str):
    timing.append(("start_run", time.perf_counter()))
    logger.info("Start running, model: %s", model)
    llm = LLM(model=model, max_model_len=300)
    timing.append(("loaded_weight", time.perf_counter()))
    prompt = "Hello vLLM!"
    timing.append(("start_inferencing", time.perf_counter()))
    logger.info("Start inferencing")
    llm.generate([prompt], sampling_params=None, use_tqdm=False)
    timing.append(("end_inferencing", time.perf_counter()))
    logger.info("Finished inferencing")


def main(opts):
    run_vllm(opts.model)
    evt, st = timing[0]
    maxlen = 1
    for e, _ in timing:
        if len(e) > maxlen:
            maxlen = len(e)
    print(RUN_NAME, f"{evt:>{maxlen}}", "at", f"{st:<16.16}")
    for e, t in timing[1:]:
        print(RUN_NAME, f"{e:>{maxlen}}", "at", f"{t:<16.16}", "delta", t - st)
        st = t
    print(RUN_NAME, "Total time", timing[-1][1] - timing[0][1])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Benchmark the Time To First Token.")
    parser.add_argument("--model", type=str)
    args = parser.parse_args()
    main(args)
