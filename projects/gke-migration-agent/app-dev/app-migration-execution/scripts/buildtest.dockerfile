# buildtest.dockerfile is used for ci.

FROM python:3.14-slim

ARG PROJECT_SUBDIRECTORY=/app
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR ${PROJECT_SUBDIRECTORY}

COPY requirements.txt ./
RUN python3 -m pip install \
    --no-cache-dir \
    --require-hashes \
    -r requirements.txt

COPY . .

ENTRYPOINT ["python3"]
CMD ["-m", "unittest", "discover", "-s", ".", "-p", "*_test.py"]
