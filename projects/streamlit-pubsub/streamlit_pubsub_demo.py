# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Demonstration of Streamlit integration with Pub/Sub.

This demonstration shows Streamlit working with Pub/Sub, integrating with
asynchronous IO.
"""


import argparse
import asyncio
import datetime
import json

import streamlit as st
from streamlit_pubsub import get_publisher, get_subscriber


def get_args():
    """Parse command line arguments for Streamlit Pub/Sub demo."""

    parser = argparse.ArgumentParser(
        prog="Streamlit PubSub Demo",
        description="Demonstration PubSub messages in Streamlit",
    )
    parser.add_argument(
        "project_id", type=str, help="Project ID for subscription"
    )
    parser.add_argument("topic_id", type=str, help="Publish Topic ID")

    return parser.parse_args()


#
# Streamlit App
#


BUFFER_SIZE = 5


args = get_args()

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Cached, so fetch as often as you need
publisher = get_publisher(args.project_id, args.topic_id)

st.title("Pub/Sub Subscription Sample")

# Create a container with a placeholder for the current time
with st.container():
    st.header("Current Time")
    st.toggle("On/Off", key="time_active", value=False)
    time_placeholder = st.empty()
    with time_placeholder.container():
        st.write(str(datetime.datetime.now()))

# Create a container with text input for publishing
with st.container():
    st.header("Publish Message")
    st.text_input(
        "Enter some message to publish",
        key="pub_msg",
        on_change=lambda: publisher(
            bytes(json.dumps({"message": st.session_state["pub_msg"]}), "utf-8")
        ),
    )

# Create a container with a placeholder for the incoming messages
with st.container():
    st.header("Subscribe Messages")
    st.toggle("On/Off", key="sub_active", value=False)
    messages_placeholder = st.empty()


# Create general tool for rendering messages
def render_messages():
    with messages_placeholder.container():
        for e in st.session_state.messages:
            st.write(e)


# Render any messages now
render_messages()


# Show_timme() displays a ticking clock. This is a demonstration of how
# asyncio can be used in streamlit as part of an updating UI.
async def show_time():
    """If active, asynchronously update the timestamp forever.

    This function is a demonstration of using asynchronous calls to poll or
    operate in the background in a running Streamlit dashboard.
    """

    if not st.session_state.time_active:
        return

    while True:

        # Render in streamlit time container
        with time_placeholder.container():
            st.write(str(datetime.datetime.now()))

        # Sleep for a second
        await asyncio.sleep(1.0)


# Read_continuously() keeps pulling out, with async, the latest data
# with a greater sequence than last time.
async def read_continuously():
    """If active, asynchronously update Pub/Sub subscription messages.

    This function is a demonstration of using asynchronous calls to fetch
    Pub/Sub messages.
    """

    if not st.session_state.sub_active:
        return

    sub = get_subscriber(
        args.project_id, args.topic_id, max_messages=BUFFER_SIZE
    )

    while True:

        data = await sub.aget_latest_st_data(seq_id_key="seq_id")

        # Add new data messages (assuming to be UTF-8 JSON strings)
        for msg in data:
            st.session_state.messages.append(json.loads(str(msg, "utf8")))

        # Purge to BUFFER_SIZE
        st.session_state.messages = st.session_state.messages[-BUFFER_SIZE:]

        # Render the messages
        render_messages()


# Dispatch tasks with asyncio
async def run_tasks():
    """Gather all of the asynchronous work -- it ends when all is done."""
    await asyncio.gather(show_time(), read_continuously())


# This creates a new event loop. We want that.
asyncio.run(run_tasks())
