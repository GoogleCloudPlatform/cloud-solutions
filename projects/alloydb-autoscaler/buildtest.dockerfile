FROM node:20-slim

ARG PROJECT_SUBDIRECTORY
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR ${PROJECT_SUBDIRECTORY}
ENTRYPOINT [ "/bin/bash", "-e", "-x", "-c" ]
CMD [ " \
  npm clean-install && \
  npm audit && \
  npm test \
" ]
