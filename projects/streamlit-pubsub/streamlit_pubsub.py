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
"""Streamlit and Pub/Sub integration methods.

These methods provide both subscription and publish functionality to
Streamlit. The subscription is much more sophisticated, as it provides a
central cache per-Subscription of received messages and allows multiple
Streamlit dashboards to share the same subscription data.
"""


import asyncio
import logging
import threading


from google.api_core.gapic_v1.client_info import ClientInfo
from google.cloud import pubsub
from google.protobuf import timestamp_pb2
import streamlit as st


logger = logging.getLogger(__name__)


class Buffer:
  """Fixed size sequence-based buffer.

  This fixed size buffer enables a subscription to add data,
  as fast as possible, and then fetch (up to the buffer size) the most recent
  N messages. A sequence number is maintained so the subscriber does not
  get duplicates, but may miss messages.
  """

  def __init__(self, max_elem=100):
    self.max_elem = max_elem
    self.data = []
    self.next_idx = 0  # zero is front of queue
    self.seq = -1  # zero is the first seqId (-1 is nothing)

  def add(self, elem):
    self.seq += 1

    if self.next_idx == len(self.data):
      self.data.append(elem)
    else:
      self.data[self.next_idx] = elem

    self.next_idx += 1
    if self.next_idx == self.max_elem:
      self.next_idx = 0

  def get_elems(self, last_seq):
    """Return all new messages since last_seq, up to max_elem."""

    required_elem = self.seq - last_seq
    if required_elem > self.max_elem:
      required_elem = self.max_elem

    if required_elem <= 0:
      return (self.seq, [])

    if required_elem <= self.next_idx:
      start_idx = self.next_idx - required_elem
      return (self.seq, self.data[start_idx:self.next_idx])

    start_end_idx = len(self.data) - required_elem + self.next_idx
    return (self.seq,
            self.data[start_end_idx:] + self.data[:self.next_idx])


class BufferedAsyncData:
  """Thread-safe Buffer wrapper with additional async methods.

  This enables sharing the buffer between threads and exposing it into
  Streamlit dashboards.
  """

  def __init__(self, max_messages=100):
    self.buf = Buffer(max_elem=max_messages)
    self.seq_id = 0
    self.cv = threading.Condition()

  def update(self, new_data: bytes):
    with self.cv:
      self.buf.add(new_data)
      self.cv.notify_all()

  def get_latest_data(self,
                      last_seq_id: int = -1,
                      timeout: float = None):
    """Thread-safe fetch of the latest data since last_seq_id.

    The timeout is used to return early if specified (empty list).

    Args:
      last_seq_id: The last sequence id (highest) that was fetched.
      timeout: The time to wait before returning empty list.

    Returns:
      A tuple of new high seq_id and a list of data. If timeout was specified,
      then the high seq_id may be the same as last_seq_id and the list
      of data empty.
    """
    while True:
      with self.cv:
        seq_id, data = self.buf.get_elems(last_seq_id)

        # If data is found, return it as is
        if data:
          return seq_id, data

        # If timed out, just return the empty data
        if not self.cv.wait(timeout=timeout):
          return seq_id, data

  async def aget_latest_data(self,
                             last_seq_id: int = -1,
                             timeout: float = None):
    return await asyncio.to_thread(
        self.get_latest_data, last_seq_id, timeout)

  async def aget_latest_st_data(self,
                                seq_id_key="key",
                                timeout: float = 1.0):
    """Get the latest data as Streamlit, using the seq_id_key.

    This is designed for a Streamlit dashboard using seq_id_key, with
    a frequent timeout.

    Args:
      seq_id_key: Key in the st.session_state for storing the seq_id.
      timeout: Timeout between loops. Recommended to be fairly small.

    Returns:
      List of data when there is new data to process.
    """

    if seq_id_key not in st.session_state:
      st.session_state[seq_id_key] = -1

    while True:
      (st.session_state[seq_id_key], data) = await self.aget_latest_data(
          last_seq_id=st.session_state[seq_id_key],
          timeout=timeout)

      # If no data (e.g., timeout occurred), just try again
      if data:
        return data


# Capture script startup time -- if seeking to now
START_TIMESTAMP = timestamp_pb2.Timestamp()
START_TIMESTAMP.GetCurrentTime()


@st.cache_resource(show_spinner=False)
def get_subscriber_client():

  # Create the subscription client and path
  return pubsub.SubscriberClient(
      # User Agent allows us to track and prioritise
      # supporting this integration
      client_info=ClientInfo(
          user_agent="cloud-solutions/streamlit-pubsub",
      )
  )


@st.cache_resource(show_spinner=False)
def get_subscriber(
    project_id: str, subscription: str,
    max_messages: int,
    seek_to_now: bool = True,
) -> BufferedAsyncData:
  """Create a new Streamlit buffer for a subscription."""

  # Create the subscription client and path
  sub = get_subscriber_client()

  # Create subscription ID
  subscription_id = sub.subscription_path(project_id, subscription)

  # Seek to now if requested
  if seek_to_now:
    sub.seek(
        request=pubsub.types.SeekRequest(
            subscription=subscription_id, time=START_TIMESTAMP)
    )

  # Create the AsyncData container and callback
  md = BufferedAsyncData(max_messages=max_messages)

  def callback(msg):
    md.update(msg.data)
    msg.ack()

  # Subscribe into the callback
  logger.info("Subscribing %s", subscription_id)
  _ = sub.subscribe(subscription_id, callback)

  return md


@st.cache_resource(show_spinner=False)
def get_publisher_client():

  # Create the subscription client and path
  return pubsub.PublisherClient(
      # User Agent allows us to track and prioritise
      # supporting this integration
      client_info=ClientInfo(
          user_agent="cloud-solutions/streamlit-pubsub",
      )
  )


@st.cache_resource(show_spinner=False)
def get_publisher(project_id: str, topic: str):

  client = get_publisher_client()
  full_topic_id = client.topic_path(project_id, topic)

  def publisher(data):
    client.publish(topic=full_topic_id, data=data)

  return publisher


