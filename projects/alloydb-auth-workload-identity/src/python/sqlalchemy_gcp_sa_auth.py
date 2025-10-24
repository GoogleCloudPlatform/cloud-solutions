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

"""
A helper function for use with sqlalchemy "do_connect" event to work
with GCP's access token.

Example:

  engine = sqlalchemy.create_engine("postgresql+psycopg://<HOST>/<DATABASE>")
  sqlalchemy_gcp_sa_auth.get_authinfo_from_gcp(engine)

"""
import json
from typing import Any, Dict, Optional, Tuple
from urllib import request

from sqlalchemy import Engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection, Dialect
from sqlalchemy.pool import ConnectionPoolEntry

USER_AGENT = "cloud-solutions/alloydb-auth-workload-identity-v0.0.1"

GCP_METADATA_SERVER_BASE = ("http://metadata.google.internal/"
                            "computeMetadata/v1/"
                            "instance/service-accounts/default/")


def fetch_and_set_username_and_token(
    cparams: Dict[str, Any]) -> None:
    """Fetch user and password from GCP metadata and set them in
    cparams.

    Args:
        cparams: the connection param to set user and password in
    """
    response = request.urlopen(
        request.Request(
            GCP_METADATA_SERVER_BASE + "email",
            headers={
                "Metadata-Flavor": "Google",
                "User-Agent": USER_AGENT
            }
        )
    )
    email = response.read().decode("utf8")
    response.close()
    pguser = email.removesuffix(".gserviceaccount.com")

    response = request.urlopen(
        request.Request(
            GCP_METADATA_SERVER_BASE + "token",
            headers={
                "Metadata-Flavor": "Google",
                "User-Agent": USER_AGENT
            }
        )
    )

    payload = json.load(response)
    response.close()
    pgpassword = payload["access_token"]
    cparams["password"] = pgpassword
    cparams["user"] = pguser


def setup_gcp_auth_hook(engine: Engine):
    """Add a "do_connect" hook to `engine`.

    The hook fetches user and password information from GCP metadata
    server on each new connection.

    Args:
        engine: the sqlalchemy engine to install the hook
    """
    def fetch_user_and_token(
        dialect: Dialect, conn_rec: ConnectionPoolEntry, cargs: Tuple[Any, ...], # pylint: disable=unused-argument
        cparams: Dict[str, Any]) -> Optional[DBAPIConnection]:
        """Provide username and password to SQLAlchemy engine.

        This is a SQLAlchemy do_connect callback function.
        """
        return fetch_and_set_username_and_token(cparams)

    event.listen_for(engine, "do_connect")(fetch_user_and_token)
