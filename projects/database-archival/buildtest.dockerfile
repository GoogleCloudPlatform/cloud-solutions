FROM python:3.9

ARG PROJECT_SUBDIRECTORY
ENV PROJECT_SUBDIRECTORY=$PROJECT_SUBDIRECTORY
WORKDIR ${PROJECT_SUBDIRECTORY}
ENTRYPOINT [ "/bin/bash", "-e", "-x", "-c" ]
CMD [ " \
    cd ${PROJECT_SUBDIRECTORY} && \
    python3 -m venv .venv && \
    . .venv/bin/activate && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-deps --require-hashes -r requirements.txt && \
    python3 -m pip install -e . && \
    python3 -m unittest discover tools '*_test.py' && \
    python3 -m airflow db init && \
    python3 -m unittest discover src/database_archival '*_test.py'" ]
