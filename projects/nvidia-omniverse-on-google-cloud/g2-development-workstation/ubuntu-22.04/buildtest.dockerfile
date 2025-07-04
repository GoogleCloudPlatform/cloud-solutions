FROM ubuntu:22.04

ARG PROJECT_SUBDIRECTORY=/app
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
ENV CONTAINERIZED_TEST_ENVIRONMENT=true
ENV DEBIAN_FRONTEND=noninteractive
ARG TZ=Etc/UTC
ENV TZ=${TZ}

WORKDIR ${PROJECT_SUBDIRECTORY}

# Need sudo to test the setup script
RUN apt-get update -y \
  && apt-get install --no-install-recommends -y \
  gpg \
  sudo \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

COPY setup-workstation.sh /

ENTRYPOINT [ "/bin/bash", "-o", "errexit", "-o", "pipefail", "-o", "nounset", "-x", "-c" ]
CMD [ "/setup-workstation.sh" ]
