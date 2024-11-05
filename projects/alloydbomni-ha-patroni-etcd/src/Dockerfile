#
# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

FROM google/alloydbomni:15

RUN apt-get update -y \
    && apt-get install --no-install-recommends -y \
        patroni=3.0.2-1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ARG PG_MAJOR=15
ARG PGHOME=/home/postgres

ENV LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    PG_MAJOR=$PG_MAJOR \
    EDITOR=/usr/bin/editor \
    PGHOME=/home/postgres \
    PGDATA=$PGHOME/data \
    PATH=$PATH:/usr/lib/postgresql/$PG_MAJOR/bin \
    ETCDCTL_API=3 \
    ENTRYPOINT_SCRIPT=entrypoint.sh

COPY "$ENTRYPOINT_SCRIPT" /

WORKDIR $PGHOME

RUN mkdir -p "$PGDATA" && chmod -R 0700 "$PGDATA" \
    && chown -R postgres:postgres "$PGHOME" /run

USER postgres

ENTRYPOINT ["sh", "-c", "sh /$ENTRYPOINT_SCRIPT"]
