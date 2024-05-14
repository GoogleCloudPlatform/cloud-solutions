# Creates a base image with
# Packages nodejs-18.12, npm, yarn-1.22.19, python 3.10, python-pip3, python venv, JDK-17, gradle-8

FROM gradle:8-jdk17-jammy
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && apt-get install --no-install-recommends -y build-essential  \
    libcurl4-openssl-dev libcurl3-gnutls git \
    python3 python3-pip python3-venv bash python-is-python3 \
    apt-transport-https ca-certificates gnupg zip unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

## Install Node \
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl https://deb.nodesource.com/setup_18.x -Lo node_setup_18.x  \
    && (echo "68b038045fa5db1fa0fb07cb00eb1c52e9ad31eb185dc94264740e903dc67317  node_setup_18.x" | sha256sum -c) \
    && curl https://registry.npmjs.org/yarn/-/yarn-1.22.19.tgz -Lo yarn-1.22.19.tgz \
    && (echo "732620bac8b1690d507274f025f3c6cfdc3627a84d9642e38a07452cc00e0f2e  yarn-1.22.19.tgz" | sha256sum -c) \
    && chmod +x node_setup_18.x && ./node_setup_18.x \
    && apt-get install --no-install-recommends -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global yarn-1.22.19.tgz \
    && rm yarn-1.22.19.tgz \
    ## Install Protoc
    && curl "https://github.com/protocolbuffers/protobuf/releases/download/v22.3/protoc-22.3-linux-x86_64.zip" -Lo "protoc.zip" \
    && (echo "0f8070d762eb8a2f5a13a47713a553f989f9d9b556e7e3ebfa2bd6464e2ecaeb  protoc.zip" | sha256sum -c) \
    && unzip protoc.zip -d /protoc

ENV PATH="${PATH}:${PWD}/protoc/bin"
