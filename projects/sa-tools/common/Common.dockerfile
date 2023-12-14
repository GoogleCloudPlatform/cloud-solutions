FROM gradle:8-jdk17-jammy AS java-builder
COPY ./common/java-common /java-common-src
WORKDIR /java-common-src
RUN gradle clean test build

FROM node:18 AS node-builder
COPY . /sa-tools-src
WORKDIR /sa-tools-src/common/ui-tests
RUN yarn install
RUN yarn style-check
RUN yarn test
