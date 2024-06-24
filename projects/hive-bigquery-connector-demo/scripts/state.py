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

"""Functions and classes to handle and represent the Terraform state.

These functions and dataclasses are designed to read, parse and expose the
terraform state to the rest of the application

Typical usage example:
from state import ScriptState
print(ScriptState.tf_state().project_id)
print(ScriptState.gcs_client())
"""

import dataclasses
import json
import multiprocessing
import typing

from google.cloud import bigquery
from google.cloud import storage


@dataclasses.dataclass(frozen=True)
class TFState:
  project_id: str
  staging_bucket: str
  warehouse_bucket: str
  dataproc_region: str
  jupyterlab_url: str
  jupyter_url: str
  dataproc_name: str
  bq_connection_location: str
  bq_connection_id: str


class ScriptState:
  """Class to read the terraform state, parse and store it.

  The class provides getter class methods to expose the state to other parts
  of the application.
  """
  __tf_state__: typing.Optional[TFState] = None
  __processes__: typing.Optional[int] = None
  __bq_client__: typing.Optional[bigquery.Client] = None
  __gcs_client__: typing.Optional[storage.Client] = None
  __dataset__: typing.Optional[bigquery.Dataset] = None

  @classmethod
  def tf_state(cls) -> TFState:
    if cls.__tf_state__ is None:
      state_file = "../terraform/terraform.tfstate"
      with open(state_file, "r", encoding="utf-8") as fp:
        full_tf_state = json.load(fp)
      full_tf_state = {
          k: v["value"] for k, v in full_tf_state["outputs"].items()}
      cls.__tf_state__ = TFState(**full_tf_state)
    return cls.__tf_state__

  @classmethod
  def bq_client(cls) -> bigquery.Client:
    if cls.__bq_client__ is None:
      cls.__bq_client__ = bigquery.Client(project=cls.tf_state().project_id)
    return cls.__bq_client__

  @classmethod
  def dataset(cls) -> bigquery.Dataset:
    if cls.__dataset__ is None:
      cls.__dataset__ = cls.bq_client().get_dataset(
          f"{cls.tf_state().project_id}.ecommerce")
    return cls.__dataset__

  @classmethod
  def gcs_client(cls) -> storage.Client:
    if cls.__gcs_client__ is None:
      cls.__gcs_client__ = storage.Client(project=cls.tf_state().project_id)
    return cls.__gcs_client__

  @classmethod
  def processes(cls) -> int:
    if cls.__processes__ is None:
      cls.__processes__ = multiprocessing.cpu_count() - 1
    return cls.__processes__
