# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=W1405, W0621, E1120, W0613, W0622

"""Unit tests for the camera_client.py module.

This module contains unit tests for the functions and classes defined in
the camera_client.py module. The tests cover various aspects of the
module's functionality, including:

- Transmitting data to MQTT and Pub/Sub.
- Reading and writing camera configurations.
- Creating payloads for Pub/Sub.
- Exiting gracefully from the application.
- Mapping integer values between ranges.
- Creating request bodies for API calls.
- Predicting results using an ML model.
- Handling MQTT connections and messages.
- Parsing command-line arguments.

Each test function is designed to isolate and test a specific aspect of
the camera_client.py module. The tests use mocking to simulate external
dependencies and ensure that the tested functions behave as expected.
"""

import base64
import json
import os
import unittest.mock as mock

import camera_client as cc
import pytest


def test_transmit_mqtt():
    """Tests the transmit_mqtt function.

    This test verifies that the transmit_mqtt function correctly calls the
    mqtt_client.publish method with the expected arguments.
    """
    # Mock the logger and mqtt_client
    logger = mock.Mock()
    mqtt_client = mock.Mock()

    # Set up the test data
    printout = True
    results = {"prediction": "some_prediction"}

    # Call the function under test
    cc.transmit_mqtt(printout, logger, mqtt_client, results, "viai/results")

    # Check that the function called the expected method
    mqtt_client.publish.assert_called_once_with(
        "viai/results", json.dumps(results)
    )


def test_transmit_pubsub():
    """Tests the transmit_pubsub function.

    This test verifies that the transmit_pubsub function correctly calls the
    publisher.publish method with the expected arguments.
    """
    # Mock the logger and publisher clients
    logger = mock.MagicMock()
    publisher = mock.MagicMock()

    # Mock the args object
    args = mock.MagicMock()
    args.project_id = "my-project"
    args.topic_id = "my-topic"
    args.pubsub = "image"

    # Mock the data object
    data = mock.MagicMock()
    data.save = mock.MagicMock()
    data.getvalue = mock.MagicMock(return_value=b"image data")

    # Call the transmit_pubsub function
    cc.transmit_pubsub(True, logger, publisher, args, data)

    # Verify that the correct methods were called
    assert publisher.publish.called
    assert publisher.publish.call_args[0][0] == (
        "projects/{}/topics/{}".format(args.project_id, args.topic_id)
    )


def test_read_config():
    """Tests the read_config function.

    This test verifies that the read_config function correctly calls the
    camera.get_properties method and writes the configuration to a file.
    """
    # Mock the camera object
    mock_cam = mock.MagicMock()
    mock_cam.get_properties.return_value = {
        "prop1": "value1",
        "prop2": "value2",
    }

    # Mock the logger object
    mock_logger = mock.MagicMock()

    # Call the read_config function
    cc.read_config(True, mock_logger, mock_cam, "mock_cfg_file.txt")

    # Assert that the expected calls were made
    mock_cam.get_properties.assert_called_once()
    mock_logger.debug.assert_called_once_with(
        "Camera properties: {'prop1': 'value1', 'prop2': 'value2'}"
    )

    # Assert that the expected file was created
    with open("mock_cfg_file.txt", "r", encoding="utf-8") as f:
        assert f.read() == "prop1 = value1\nprop2 = value2\n"
    os.remove("mock_cfg_file.txt")


def test_create_pubsub_payload():
    """Tests the create_pubsub_payload function.

    This test verifies that the create_pubsub_payload function correctly
    creates a binary payload for ML inference results and thermal camera
    raw data.
    """

    # Mock the logger object
    mock_logger = mock.MagicMock()

    # Test case 1: ML inference results payload
    r = {"results": {"score": 0.5}}
    payload = cc.create_pubsub_payload(r, mock_logger)
    assert payload is not None
    assert isinstance(payload, bytes)

    # Test case 2: Thermal camera raw data payload
    r = {
        "device_id": "device_123",
        "ts": "2023-03-08 12:30:00",
        "temp_format": "celsius",
        "temp_avg": 37.2,
        "temp_min": 36.5,
        "temp_max": 37.9,
        "temp_array": [35, 36, 37, 38, 39],
    }
    payload = cc.create_pubsub_payload(r, mock_logger)
    assert payload is not None
    assert isinstance(payload, bytes)

    # Test case 3: Unknown input data format
    r = {"invalid_key": "invalid_value"}
    payload = cc.create_pubsub_payload(r, mock_logger)
    assert payload is None


def test_write_config(mocker):
    """Tests the write_config function.

    This test verifies that the write_config function correctly calls the
    camera.set_properties method with the expected configurations.

    Args:
      mocker: Mock object for the mocker module.
    """
    # Mock the logger and cam objects
    logger = mocker.Mock()
    cam = mocker.Mock()

    # Mock the open() function to return a file object
    file_object = mocker.mock_open(read_data="key = 1")
    mocker.patch("builtins.open", file_object)

    # Call the write_config() function with mocked objects
    cc.write_config(True, logger, cam, "cfg_file.txt")

    # Assert that the expected methods were called
    assert cam.set_properties.called_once
    assert logger.debug.called_once

    # Assert that the correct configurations were written to the camera
    expected_configs = {"key": 1}
    assert cam.set_properties.call_args[0][0] == expected_configs


def test_exit_gracefully():
    """Tests the exit_gracefully function.

    This test verifies that the exit_gracefully function correctly calls
    the camera.close and mqtt_client.loop_stop methods.
    """
    # Mock the system exit function
    with mock.patch("sys.exit"):
        # Create a mock camera and MQTT client
        mock_cam = mock.Mock()
        mock_mqtt_client = mock.Mock()

        # Call the exit_gracefully function
        with pytest.raises(SystemExit):
            cc.exit_gracefully(mock_cam, mock_mqtt_client)

    # Assert that the camera and MQTT client were closed
    assert mock_cam.close.called
    assert mock_mqtt_client.loop_stop.called


def test_int_map_range():
    """Tests the int_map_range function.

    This test verifies that the int_map_range function correctly maps
    an input value from one range to another.
    """
    assert cc.int_map_range(0, 0, 100, 0, 255) == 0
    assert cc.int_map_range(50, 0, 100, 0, 255) == 127
    assert cc.int_map_range(100, 0, 100, 0, 255) == 255


def test_create_request_body():
    """Tests the create_request_body function.

    This test verifies that the create_request_body function correctly
    creates a JSON request body for the API call.
    """
    # Test case 1: Valid image data
    image_data = b"valid_image_data"
    request_body_template = '{ "image_data": "{encoded_string}" }'
    request_body = cc.create_request_body(image_data, request_body_template)
    expected_body = json.dumps(
        {"image_data": base64.b64encode(image_data).decode("utf-8")})
    assert request_body == expected_body

    # Test case 2: Empty image data
    image_data = b""
    request_body = cc.create_request_body(image_data, request_body_template)
    expected_body = json.dumps(
        {"image_data": base64.b64encode(image_data).decode("utf-8")})
    assert request_body == expected_body

def test_predict():
    """Tests the predict function.

    This test verifies that the predict function correctly sends a POST
    request to the API endpoint and returns the predicted results.
    """
    image_data = b"some_image_bytes"
    ml_url = "http://test_hostname:8000/v1/visualInspection:predict"
    request_body_template = '{ "image_data": "{encoded_string}" }'

    mock_response_json = {"prediction": "some_result"}

    with mock.patch("requests.post") as mock_requests_post:
        mock_requests_post.return_value.status_code = 200
        mock_requests_post.return_value.json.return_value = mock_response_json

        mock_logger = mock.Mock()
        result = cc.predict(False, mock_logger, image_data, ml_url,
                            request_body_template)

    assert result == mock_response_json
    mock_requests_post.assert_called_once_with(ml_url, data=mock.ANY)
    mock_logger.debug.assert_has_calls(
        [mock.call(f"Sending image to ML URL: {ml_url}"), mock.call(mock.ANY)]
    )


def test_mqtt_on_connect(mocker):
    """Tests the mqtt_on_connect function.

    This test verifies that the mqtt_on_connect function correctly calls
    the MQTT client's subscribe method with the expected topic and QoS.

    Args:
      mocker: Mock object for the mocker module.
    """
    # Mock the MQTT client and userdata
    client = mocker.Mock()
    userdata = "viai/commands"

    # Mock the MQTT flags and return code
    flags = mocker.Mock()
    rc = mocker.Mock()

    # Mock the MQTT client's subscribe method
    client.subscribe.return_value = (0, 1)

    # Call the MQTT on connect callback
    cc.mqtt_on_connect(client, userdata, flags, rc)

    # Verify that the MQTT subscribe method was called with right topic & QoS
    client.subscribe.assert_called_once_with("viai/commands/#", qos=0)

    # Verify that the MQTT subscribe method returned correct result code
    assert client.subscribe.return_value == (0, 1)


def test_parse_args():
    """Tests the parse_args function.

    This test verifies that the parse_args function correctly parses
    command-line arguments.
    """
    with mock.patch(
        "sys.argv",
        ["camera_client.py", "--log", "debug", "--ml", "--width", "1280"],
    ):
        args = cc.parse_args()

        assert args.log == "debug"
        assert args.ml
        assert args.width == 1280
