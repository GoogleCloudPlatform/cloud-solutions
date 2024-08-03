# syntax=docker/dockerfile:1

# Note: Use this Dockerfile from the /projects/sa-tools/ and not
# from the gke-optimization/binpacker folder.

### Use node image as a builder for UI
FROM node:18.20.4-alpine

# Install required packages
RUN apk update && apk add --no-cache protobuf-dev

ARG PROJECT_SUBDIRECTORY
WORKDIR "${PROJECT_SUBDIRECTORY}"

ENTRYPOINT [ "/bin/sh", "-e", "-x", "-c" ]
CMD [ " \
    cd ../../common/ui && yarn install && cd - && \
    yarn install && \
    yarn audit && \
    yarn build \
  " ]
