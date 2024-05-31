# Streamlit PubSub Demo

## Overview

This is a demonstration of pulling real-time streaming data from Pub/Sub into
Streamlit.

Subscriber behaviour:

* There is a configurable fixed buffer of messages it retains. Clients will
  receive all messages back in time up to this buffer size.
* Each client session will receive messages as fast as possible asynchronously.
* Only one subscription is shared (for the subscription) across all user sessions.

Note that asyncio isn't officially supported by Streamlit (see [this](https://github.com/streamlit/streamlit/issues/8488)),
but this use of it should be safe. Each rendering of the page has its own async
loop, with the loop shutting down if the page is reloaded.

## Creating topic and subscription

It is necessary to create a topic and a subscription to the topic. In this case,
`echo-json` is the topic name and `echo-json-sub` is the subscription.

```bash
gcloud pubsub subscriptions create --topic=echo-json echo-json-sub
gcloud pubsub topics create echo-json
```

## Initializing Python Environment

The Python environment needs to be initialized. You can use the following or your
favourite tools.

```bash
python3 -m venv .venv
.venv/bin/python3 -m ensurepip
.venv/bin/python3 -m pip install --require-hashes -r requirements.txt
source .venv/bin/activate
```

## Running Streamlit

Start Streamlit to show a dashboard, connecting to the subscription and topic. Replace
`PROJECT_ID` with the project you created the subscription in.

```bash
streamlit run streamlit_pubsub_demo.py -- PROJECT_ID echo-json-sub echo-json
```

## [Optional] Publishing data to PubSub

Start publishing messages to the topic. Replace `PROJECT_ID` with the project you
created the topic in.

```bash
python3 publish_to_pubsub.py PROJECT_ID echo-json
```
