FROM python:3.8.18 as base

SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]

RUN apt-get update \
    && apt-get --assume-yes --no-install-recommends install \
    apt-transport-https \
    curl \
    git \
    gnupg \
    libusb-1.0-0 \
    lsb-release \
    make \
    openssh-client \
    libopencv-dev python3-opencv \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

ENV WORKDIR_PATH=/opt/app
RUN mkdir -p "${WORKDIR_PATH}"
WORKDIR "${WORKDIR_PATH}"

COPY base-tooling-requirements.txt base-tooling-requirements.txt
RUN python3 -m pip install --no-deps --require-hashes \
    --no-cache-dir -r base-tooling-requirements.txt

COPY requirements.txt requirements.txt
RUN python3 -m pip install --require-hashes --no-deps --no-cache-dir -r requirements.txt

COPY cameras.proto "${WORKDIR_PATH}"/
RUN protoc -I="${WORKDIR_PATH}" --python_out="${WORKDIR_PATH}" "${WORKDIR_PATH}"/cameras.proto

FROM base as camera-integration-test

COPY tests/requirements-dev.txt tests/requirements-dev.txt
RUN python3 -m pip install --require-hashes --no-deps --no-cache-dir -r tests/requirements-dev.txt

COPY . "${WORKDIR_PATH}"/
RUN python3 -m pytest tests/

FROM camera-integration-test as camera-integration

ARG CLOUD_SDK_VERSION=445.0.0
ENV CLOUD_SDK_VERSION=$CLOUD_SDK_VERSION

# hadolint ignore=DL4006
RUN CLOUD_SDK_REPO="cloud-sdk-$(lsb_release -c -s)" \
    && export CLOUD_SDK_REPO \
    && echo "deb https://packages.cloud.google.com/apt ${CLOUD_SDK_REPO} main" > /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    google-cloud-sdk=${CLOUD_SDK_VERSION}-0 \
    && rm -rf /var/lib/apt/lists/* \
    && gcloud --version

RUN git config --system credential.'https://source.developers.google.com'.helper gcloud.sh

ENV PATH="${PATH}:/opt/google-cloud-sdk/bin/"

ENTRYPOINT ["python3", "camera_client.py"]

CMD ["--help"]
