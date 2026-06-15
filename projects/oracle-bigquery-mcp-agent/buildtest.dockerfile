FROM hashicorp/terraform:1.9.4

ARG PROJECT_SUBDIRECTORY=/app
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR ${PROJECT_SUBDIRECTORY}

# Ash execution entrypoint validating HCL syntax compliance across all five root modules
ENTRYPOINT ["/bin/ash", "-e", "-x", "-c"]
CMD [ " \
  if [ -d datastream-bq ]; then \
    cd datastream-bq && \
    terraform init -input=false -no-color && \
    terraform validate -no-color && \
    cd ..; \
  fi && \
  if [ -d dialogflow-cx-agent-tf ]; then \
    cd dialogflow-cx-agent-tf && \
    terraform init -input=false -no-color && \
    terraform validate -no-color && \
    cd ..; \
  fi && \
  if [ -d looker-core-tf ]; then \
    cd looker-core-tf && \
    terraform init -input=false -no-color && \
    terraform validate -no-color && \
    cd ..; \
  fi && \
  if [ -d mcp-server-tf ]; then \
    cd mcp-server-tf && \
    terraform init -input=false -no-color && \
    terraform validate -no-color && \
    cd ..; \
  fi && \
  if [ -d ora-vm-tf-19c ]; then \
    cd ora-vm-tf-19c && \
    terraform init -input=false -no-color && \
    terraform validate -no-color && \
    cd ..; \
  fi" ]
