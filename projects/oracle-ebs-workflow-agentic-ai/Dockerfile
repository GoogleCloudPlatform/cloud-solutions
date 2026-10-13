# Copyright 2026 Google LLC
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

FROM python:3.14-slim AS builder

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/oracle/network/admin \
    && curl -fsSL https://download.oracle.com/otn_software/linux/instantclient/1925000/instantclient-basiclite-linux.x64-19.25.0.0.0dbru.zip -o /tmp/ic.zip \
    && echo "0112b0aa477e679a66e37db93e1dc6460b4f270746cd094b348effaf2fe913d4  /tmp/ic.zip" | sha256sum -c - \
    && unzip -q /tmp/ic.zip -d /opt/oracle \
    && mv /opt/oracle/instantclient_19_25 /opt/oracle/instantclient \
    && rm -f /tmp/ic.zip \
    && printf "SQLNET.ALLOWED_LOGON_VERSION_CLIENT = 8\nSQLNET.ALLOWED_LOGON_VERSION_SERVER = 8\n" > /opt/oracle/network/admin/sqlnet.ora

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install verified runtime dependencies into isolated venv
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt


FROM python:3.14-slim AS runtime

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libaio1t64 libnsl2 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1

# Copy isolated virtual environment and Oracle Instant Client without build tools
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/oracle /opt/oracle

# Copy source code with non-root ownership
COPY --chown=nobody:nogroup src/ /app/src/

# Environment defaults
ENV PATH="/opt/venv/bin:$PATH"
ENV LD_LIBRARY_PATH="/opt/oracle/instantclient"
ENV TNS_ADMIN="/opt/oracle/network/admin"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/tmp
ENV PORT=8080

USER nobody

ENTRYPOINT ["uvicorn"]
CMD ["src.a2a.a2a_server:app", "--host", "0.0.0.0", "--port", "8080"]
