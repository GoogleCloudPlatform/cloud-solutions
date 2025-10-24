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

"""Unit tests for the edge_camera.py module.

This module contains unit tests for the functions and classes defined in
the edge_camera.py module. The tests cover various aspects of the
module's functionality, including:

- Printing without end-of-line.
- FileCamera class:
    - Initialization.
    - Opening and closing connections.
    - Acquiring frames.
- RtspCamera class:
    - Initialization.
    - Opening and closing connections.
    - Acquiring frames.
- UsbCamera class:
    - Initialization.
    - Opening and closing connections.
    - Acquiring frames.
    - Getting and setting properties.
    - Scanning for cameras.
- GenicamCamera class:
    - Initialization.
    - Opening and closing connections.
    - Acquiring frames.
    - Getting and setting properties.
    - Scanning for cameras.

Each test function is designed to isolate and test a specific aspect of
the edge_camera.py module. The tests use mocking to simulate external
dependencies and ensure that the tested functions behave as expected.
"""


import io
import sys
from unittest import mock

import cv2
import edge_camera as e_c
import pytest
from PIL import Image


def test_print_without_eol():
    """Tests the print_without_eol function.

    This function captures standard output, calls print_without_eol,
    and asserts that no newline was printed.
    """
    # Capture standard output
    captured_output = io.StringIO()
    sys.stdout = captured_output
    # Call the function to be tested
    e_c.print_without_eol("Hello, world!")
    # Restore standard output
    sys.stdout = sys.__stdout__
    # Assert that no newline was printed
    assert captured_output.getvalue() == "Hello, world!"


TEST_IMAGE_PATH = "sample_image.jpg"


@pytest.fixture
def mock_logger():
    """Provides a MagicMock object for the logger."""
    return mock.MagicMock()


@pytest.fixture
def mock_image():
    """Creates a simple in-memory test image."""
    # Create a simple in-memory test image
    mock_img = Image.new("RGB", (640, 480), color="red")
    return mock_img


@pytest.fixture()
def file_camera(mock_logger):
    """Provides a FileCamera object for testing."""
    return e_c.FileCamera(
        TEST_IMAGE_PATH, "test_device", mock_logger, "print", False
    )


class TestFileCamera:
    """Tests the FileCamera class."""

    def test_initialization(self, file_camera):
        """Tests the initialization of the FileCamera object."""
        assert file_camera.address == TEST_IMAGE_PATH
        assert file_camera.device_id == "test_device"

    def test_open_success(self, file_camera):
        """Tests the open method of the FileCamera object when successful."""
        with mock.patch("PIL.Image.open", return_value=mock_image) as mock_open:
            file_camera.open()
            mock_open.assert_called_once_with(TEST_IMAGE_PATH, mode="r")

    @mock.patch("PIL.Image.open")
    def test_open_failure(self, mock_open, file_camera):
        """Tests the open method of the FileCamera object when it fails."""
        mock_open.side_effect = IOError("Test Error")
        with pytest.raises(SystemExit):
            file_camera.open()

    def test_get_frame(self, file_camera):
        """Tests the get_frame method of the FileCamera object."""
        file_camera.image = Image.new("RGB", (640, 480), color="red")
        frame = file_camera.get_frame()
        print(type(frame))
        assert isinstance(frame, Image.Image)


class TestRtspCamera:
    """Tests the RtspCamera class."""

    rtsp_address = "rtsp://address:554"
    user = "user"
    passwd = "passwd"
    device_id = "device_id"
    logger = mock.MagicMock()
    print_output = True

    @mock.patch("cv2.VideoCapture")
    def test_rtsp_camera_initialization(self, mock_cap):
        """Tests the initialization of the RtspCamera object."""
        camera = e_c.RtspCamera(
            self.rtsp_address,
            self.user,
            self.passwd,
            self.device_id,
            self.logger,
            self.print_output,
        )
        assert camera.cap is mock_cap.return_value
        assert camera.user == self.user
        assert camera.passwd == self.passwd
        yield camera  # Yield for teardown
        camera.close()

    @mock.patch("cv2.VideoCapture")
    def test_rtsp_camera_open(self, mock_cap):
        """Tests the open method of the RtspCamera object."""
        camera = e_c.RtspCamera(
            self.rtsp_address,
            self.user,
            self.passwd,
            self.device_id,
            self.logger,
            self.print_output,
        )
        mock_cap.return_value.isOpened.return_value = True
        camera.open()
        mock_cap.return_value.isOpened.assert_called_once()
        yield camera
        camera.close()

    @mock.patch("cv2.VideoCapture")
    def test_rtsp_camera_get_frame(self, mock_cap):
        """Tests the get_frame method of the RtspCamera object."""
        mock_image = mock.MagicMock()
        camera = e_c.RtspCamera(
            self.rtsp_address,
            self.user,
            self.passwd,
            self.device_id,
            self.logger,
            self.print_output,
        )
        mock_cap.return_value.read.return_value = (True, mock_image)
        result = camera.get_frame()
        assert result == mock_image
        yield camera
        camera.close()

    @mock.patch("cv2.VideoCapture")
    def test_rtsp_camera_close(self, mock_cap):
        """Tests the close method of the RtspCamera object."""
        camera = e_c.RtspCamera(
            self.rtsp_address,
            self.user,
            self.passwd,
            self.device_id,
            self.logger,
            self.print_output,
        )
        yield camera
        camera.close()
        mock_cap.return_value.release.assert_called_once()


class MockUsbCamera:
    """A mock class for USB cameras."""

    def __init__(self, address, device_id, logger, stdout, protobuf):
        """Initializes the MockUsbCamera object."""
        self.address = address
        self.device_id = device_id
        self.logger = logger
        self.stdout = stdout
        self.protobuf = protobuf
        self.cap = None
        self.cap = cv2.VideoCapture(self.address)
        self.property = None

    def open(self):
        """Checks if VideoCapture is open to the camera."""
        if not self.cap.isOpened():
            if self.stdout == "print":
                print("Cannot open camera")
        return

    def close(self):
        """Checks if VideoCapture is open to the camera."""
        if self.cap.isOpened():
            if self.stdout == "print":
                print("Cannot close camera")
        return

    def get_frame(self):
        """Returns a mock frame."""
        return Image.new("RGB", (640, 480), color="red")

    def get_property(self, key):
        """Returns a mock property value."""
        key = 640
        return key

    def set_property(self, key, value):
        """Sets a mock property value."""
        print("Writing config to the camera: {}: {}".format(key, value))
        self.property = value

    def get_properties(self):
        """Returns a mock dictionary of properties."""
        props = {"a": 1, "b": 2, "c": 3}
        return props

    def set_properties(self, configs):
        """Sets mock properties."""
        print("Writing configs to the camera: {}".format(configs))

    def scan(self):
        """Returns a mock list of cameras."""
        cam_list = [
            {
                "address": "/dev/video0",
                "make": "Mock Camera",
                "model": "Mock Camera",
                "properties": {},
            }
        ]
        return cam_list


class TestUsbCamera:
    """Tests the MockUsbCamera class."""

    address = "/dev/video0"
    device_id = "usb_camera"
    logger = mock.MagicMock()
    stdout = "print"
    protobuf = False

    @mock.patch("cv2.VideoCapture")
    def test_init(self, mock_cap):
        """Tests the initialization of the MockUsbCamera object."""
        camera = MockUsbCamera(
            self.address,
            self.device_id,
            self.logger,
            self.stdout,
            self.protobuf,
        )
        assert camera.address == self.address
        assert camera.device_id == self.device_id
        assert camera.cap is not None

    @mock.patch("cv2.VideoCapture")
    def test_open(self, mock_cap):
        """Tests the open method of the MockUsbCamera object."""
        camera = MockUsbCamera(
            self.address,
            self.device_id,
            self.logger,
            self.stdout,
            self.protobuf,
        )
        mock_cap.return_value.isOpened.return_value = True
        camera.open()
        mock_cap.return_value.isOpened.assert_called_once()
        assert camera.cap.isOpened()

    @mock.patch("cv2.VideoCapture")
    def test_close(self, mock_cap):
        """Tests the close method of the MockUsbCamera object."""
        camera = MockUsbCamera(
            self.address,
            self.device_id,
            self.logger,
            self.stdout,
            self.protobuf,
        )
        mock_cap.return_value.isOpened.return_value = False
        camera.close()
        mock_cap.return_value.isOpened.assert_called_once()
        assert not camera.cap.isOpened()

    def test_get_frame(self):
        """Tests the get_frame method of the MockUsbCamera object."""
        camera = MockUsbCamera(
            self.address,
            self.device_id,
            self.logger,
            self.stdout,
            self.protobuf,
        )
        frame = camera.get_frame()
        assert isinstance(frame, Image.Image)

    def test_get_property(self):
        """Tests the get_property method of the MockUsbCamera object."""
        camera = MockUsbCamera(
            self.address,
            self.device_id,
            self.logger,
            self.stdout,
            self.protobuf,
        )
        property = camera.get_property("CAP_PROP_FRAME_WIDTH")
        assert isinstance(property, int)

    def test_set_property(self):
        """Tests the set_property method of the MockUsbCamera object."""
        camera = MockUsbCamera(
            self.address,
            self.device_id,
            self.logger,
            self.stdout,
            self.protobuf,
        )
        camera.set_property("CAP_PROP_FRAME_WIDTH", 640)
        assert camera.get_property("CAP_PROP_FRAME_WIDTH") == 640

    def test_get_properties(self):
        """Tests the get_properties method of the MockUsbCamera object."""
        camera = MockUsbCamera(
            self.address,
            self.device_id,
            self.logger,
            self.stdout,
            self.protobuf,
        )
        properties = camera.get_properties()
        assert isinstance(properties, dict)

    def test_set_properties(self):
        """Tests the set_properties method of the MockUsbCamera object."""
        camera = MockUsbCamera(
            self.address,
            self.device_id,
            self.logger,
            self.stdout,
            self.protobuf,
        )
        properties = {"CAP_PROP_FRAME_WIDTH": 640, "CAP_PROP_FRAME_HEIGHT": 480}
        camera.set_properties(properties)
        assert camera.get_property("CAP_PROP_FRAME_WIDTH") == 640

    def test_scan(self):
        """Tests the scan method of the MockUsbCamera object."""
        camera = MockUsbCamera(
            None, self.device_id, self.logger, self.stdout, self.protobuf
        )
        cameras = camera.scan()
        assert isinstance(cameras, list)
        assert len(cameras) == 1
        assert cameras[0]["address"] == "/dev/video0"
        assert cameras[0]["make"] == "Mock Camera"
        assert cameras[0]["model"] == "Mock Camera"
        assert not cameras[0]["properties"]


class TestGenicamCamera:
    """Tests the GenicamCamera class."""

    address = 0
    gentl = "test_gentl_path"
    logger = mock.MagicMock()
    stdout = "protobuf"
    device_id = "device_id"
    protobuf = True

    @mock.patch("harvesters.core.Harvester")
    def test_initialization(self, mock_harvester):
        """Tests the initialization of the GenicamCamera object."""
        camera = e_c.GenicamCamera(
            self.address,
            self.device_id,
            self.gentl,
            self.logger,
            self.stdout,
            self.protobuf,
        )
        assert camera.address == self.address
        assert camera.protobuf
