FROM google/alloydbomni:15

RUN apt-get update -y \
    && apt-get install --no-install-recommends -y \
        patroni=3.0.2-1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ARG PG_MAJOR=15
ARG PGHOME=/home/postgres

ENV LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    PG_MAJOR=$PG_MAJOR \
    EDITOR=/usr/bin/editor \
    PGHOME=/home/postgres \
    PGDATA=$PGHOME/data \
    PATH=$PATH:/usr/lib/postgresql/$PG_MAJOR/bin \
    ETCDCTL_API=3 \
    ENTRYPOINT_SCRIPT=entrypoint.sh

COPY "$ENTRYPOINT_SCRIPT" /

WORKDIR $PGHOME

RUN mkdir -p "$PGDATA" && chmod -R 0700 "$PGDATA" \
    && chown -R postgres:postgres "$PGHOME" /run

USER postgres

ENTRYPOINT ["sh", "-c", "sh /$ENTRYPOINT_SCRIPT"]
