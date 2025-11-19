FROM node:21-slim

ARG PROJECT_SUBDIRECTORY=/app
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR ${PROJECT_SUBDIRECTORY}
ENTRYPOINT [ "/bin/bash", "-e", "-x", "-c" ]
CMD [ " \
  npm clean-install && \
  npm audit && \
  npm test \
  " ]
