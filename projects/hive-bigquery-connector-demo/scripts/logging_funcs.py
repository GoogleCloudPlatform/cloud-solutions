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

"""Functions for setting up logging."""

import atexit
import json
import logging
import logging.config
import logging.handlers
import pathlib


def setup_logging():
  """Set up logging."""
  config_file = pathlib.Path("logging.config.json")
  with open(config_file, encoding="utf-8") as f_in:
    config = json.load(f_in)

  logging.config.dictConfig(config)

  # In 3.12, logging.getHandlerByName is a thing, but for <=3.11 read the
  # dict from the json file
  # queue_handler = logging.getHandlerByName("queue_handler")

  queue_handler = config["handlers"].get("queue_handler")
  if queue_handler is not None:
    queue_handler.listener.start()
    atexit.register(queue_handler.listener.stop)
