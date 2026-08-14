# buildtest.dockerfile is used for ci.

FROM python:3.10-slim

ARG PROJECT_SUBDIRECTORY=/app
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR ${PROJECT_SUBDIRECTORY}

COPY requirements.txt ./
RUN python3 -m pip install \
    --no-cache-dir \
    --require-hashes \
    -r requirements.txt

ENTRYPOINT [ "/bin/bash", "-e", "-x", "-c" ]
CMD [ " \
  python3 -m py_compile *.py \
" ]
