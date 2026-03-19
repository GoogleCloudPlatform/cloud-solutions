FROM gcr.io/k8s-skaffold/skaffold:v2.18.0 AS skaffold

FROM golang:1.26

COPY --from=skaffold /usr/bin/skaffold /usr/bin/skaffold

ARG PROJECT_SUBDIRECTORY=/app
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR "${PROJECT_SUBDIRECTORY}"

ENTRYPOINT [ "/bin/sh", "-e", "-x", "-c" ]
CMD [ " \
  skaffold build --cache-artifacts=false --push=false \
  " ]
