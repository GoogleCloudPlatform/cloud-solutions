# syntax=docker/dockerfile:1

# Note: Use this Dockerfile from the project folder (/projects/sa-tools/) and
# not from the common (/projects/sa-tools/common/) folder.

FROM gradle:8-jdk17-jammy AS java-builder
COPY ./common/java-common /java-common-src
WORKDIR /java-common-src
RUN gradle clean test build

FROM node:18 AS node-builder
COPY . /sa-tools-src
WORKDIR /sa-tools-src/common/ui-tests
RUN yarn install \
    && yarn cache clean \
    && yarn style-check \
    && yarn test
