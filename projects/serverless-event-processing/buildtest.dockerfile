FROM hashicorp/terraform:1.9.4

ARG PROJECT_SUBDIRECTORY
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR ${PROJECT_SUBDIRECTORY}
ENTRYPOINT [ "/bin/ash", "-e", "-x", "-c" ]
CMD [ " \
  cd terraform || exit 1 && \
  terraform init -input=false && \
  terraform validate" ]
