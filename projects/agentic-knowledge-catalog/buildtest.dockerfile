FROM hashicorp/terraform:1.15.6

ARG PROJECT_SUBDIRECTORY=/app
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR ${PROJECT_SUBDIRECTORY}
ENTRYPOINT [ "/bin/ash", "-e", "-x", "-c" ]
CMD [ " \
  terraform init -input=false -no-color -lockfile=readonly && \
  terraform validate -no-color" ]
