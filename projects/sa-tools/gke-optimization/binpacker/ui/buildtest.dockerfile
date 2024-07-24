# syntax=docker/dockerfile:1

# Note: Use this Dockerfile from the /projects/sa-tools/ and not
# from the gke-optimization/binpacker folder.

### Use node image as a builder for UI
FROM node:18-alpine
ARG PROJECT_SUBDIRECTORY
WORKDIR "${PROJECT_SUBDIRECTORY}"

# Install required packages
RUN apk update && apk add --no-cache protobuf-dev

ENTRYPOINT [ "/bin/sh", "-e", "-x", "-c" ]
CMD [ " \
    cd ../../../common/ui && yarn install --cache-folder=/tmp/npm && cd - && \
    yarn install --cache-folder=/tmp/npm && \
    yarn genproto && \
    yarn audit --cache-folder=/tmp/npm && \
    yarn test \
  " ]
