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

# pylint: disable=W1405
# ruff: noqa

"""Edge camera helper functions.

This module provides a set of camera classes for interacting with
different types of cameras, including:

- **FileCamera:** Reads image files as a camera source.
- **RtspCamera:** Connects to RTSP streams using OpenCV.
- **OnvifCamera:** Extends RTSP with ONVIF support for discovery and
  configuration.
- **UsbCamera:** Connects to USB cameras using OpenCV.
- **GenicamCamera:** Connects to Genicam/GigE Vision cameras using
  the harvesters library.

Each camera class implements common methods for:

- **Opening and closing connections:** `open()`, `close()`
- **Acquiring frames:** `get_frame()`
- **Health checks:** `health_check()`
- **Configuration management (for configurable cameras):**
  `get_property()`, `set_property()`, `get_properties()`,
  `set_properties()`, `scan()`

This module also provides helper functions for:

- **Printing without end-of-line:** `print_without_eol()`
- **Creating protobuf messages:** `cameras_pb2`

This module is designed to be used in conjunction with the
`camera_client.py` script, which provides a command-line interface
for interacting with cameras and running ML inference.
"""

import abc
import io
import os
import threading
import urllib
import warnings

import cameras_pb2
import cv2
from harvesters.core import Harvester
import numpy as np
import onvif
import PIL
from PIL import Image
import wsdiscovery
from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery

warnings.filterwarnings("ignore", category=DeprecationWarning)

def print_without_eol(mystr):
    """Prints a string without an end-of-line character.

    Args:
      mystr: The string to print.
    """
    print(mystr, end="")


class BasicCamera(abc.ABC):
    """Abstract basic camera definition.

    Abstract definition of a generic camera class.
    No implementations.

    Attributes:
      address: str
      device_id: str
    """

    address: str = NotImplemented
    device_id: str = NotImplemented

    @abc.abstractmethod
    def open(self):
        """Opens the camera connection."""
        raise NotImplementedError()

    @abc.abstractmethod
    def close(self):
        """Closes the camera connection."""
        raise NotImplementedError()

    @abc.abstractmethod
    def get_frame(self):
        """Gets a frame from the camera."""
        raise NotImplementedError()

    @abc.abstractmethod
    def health_check(self):
        """Checks if the camera is working normally."""
        raise NotImplementedError()


class ConfigurableCamera(BasicCamera):
    """Abstract configurable camera definition.

    Abstract definition of a configurable camera class.
    Similar to BasicCamera, with additional abstract
    methods, for camera config control and scanning.
    """

    @abc.abstractmethod
    def get_property(self):
        """Gets a configuration parameter's value from the camera."""
        raise NotImplementedError()

    @abc.abstractmethod
    def set_property(self):
        """Sets a configuration parameter's value on the camera."""
        raise NotImplementedError()

    @abc.abstractmethod
    def get_properties(self):
        """Gets all configurations from the camera."""
        raise NotImplementedError()

    @abc.abstractmethod
    def set_properties(self):
        """Sets all configurations on the camera."""
        raise NotImplementedError()

    @abc.abstractmethod
    def scan(self):
        """Scans for connected cameras."""
        raise NotImplementedError()


class FileCamera(BasicCamera):
    """File type camera class.

    Implements a camera class based on reading input files.
    Input files are valid image files that can be used as a
    camera, when the actual camera cannot be integrated with.

    Attributes:
      address: str
      device_id: str
      logger: logging.Logger
      stdout: str
      protobuf: bool
      cam_proto: cameras_pb2.Camera
      health_proto: cameras_pb2.CameraHealthCheckResult
      frame_proto: cameras_pb2.CameraFrameResult
      printout: bool
      image: PIL.Image
    """

    def __init__(self, address, device_id, logger, stdout, protobuf):
        """Initializes the instance based on input image file path.

        Args:
          address: str
          device_id: str
          logger: logging.Logger
          stdout: str
          protobuf: bool
        """
        self.address = address
        self.device_id = device_id
        self.logger = logger
        self.stdout = stdout
        self.protobuf = protobuf
        self.cam_proto = cameras_pb2.Camera()
        self.health_proto = cameras_pb2.CameraHealthCheckResult()
        self.frame_proto = cameras_pb2.CameraFrameResult()

        self.printout = self.stdout == "print"
        self.image = None
        if self.printout:
            print("Processing image file: {}".format(self.address))
        if self.address:
            stream_proto = cameras_pb2.Camera.Stream()
            stream_proto.protocol = cameras_pb2.Camera.Stream.PROTOCOL_FILE
            stream_proto.address = self.address
            self.cam_proto.streams.append(stream_proto)
            self.cam_proto.make = "File"
            self.cam_proto.model = "System"
            self.logger.debug(
                "Opening capture connection to: {}".format(self.address)
            )
            self.logger.debug(self.cam_proto)

    def open(self):
        """Opens the source image as a connected camera."""
        if self.image:
            self.close()
        try:
            if self.printout:
                self.logger.debug("Opening image: {}".format(self.address))
            self.image = Image.open(self.address, mode="r")
        except FileNotFoundError as e1:
            if self.printout:
                print(f"Error: {e1!r}")
                self.logger.error("Cannot find image as camera")
            exit(1)
        except PIL.UnidentifiedImageError as e2:
            if self.printout:
                print(e2)
                self.logger.error("Cannot open image as camera")
            exit(1)
        except IOError as e3:
            if self.printout:
                print(e3)
                self.logger.error("Cannot open image as camera")
            exit(1)

    def close(self):
        """Closes the source image file."""
        if self.image:
            if self.printout:
                self.logger.debug("Closing image: {}".format(self.address))
            self.image.close()
            self.image = None

    def get_frame(self):
        """Reads the source image as a frame.

        Returns:
          PIL.Image: image frame
          self.frame_proto: protobuf frame
        """
        try:
            if self.printout:
                self.logger.debug("Reading image: {}".format(self.address))
            self.image.load()
        except IOError as e1:
            if self.printout:
                print(f"Error: {e1!r}")
            return None
        except MemoryError as e2:
            if self.printout:
                print(e2)
            return None
        if not self.protobuf:
            return self.image

        buf = io.BytesIO()
        self.image.save(buf, format="PNG")
        buf.seek(0)
        self.frame_proto.png_frame = buf.read()
        self.frame_proto.camera.CopyFrom(self.cam_proto)
        return self.frame_proto.SerializeToString().decode("utf-8")

    def health_check(self):
        """Checks if the image can be read.

        Returns:
          bool: True if the image can be read, False otherwise.
          str: Protobuf string if protobuf is True, None otherwise.
        """
        image = self.get_frame()
        if not image:
            if self.printout:
                print("Error reading frame.")
                return False
            if self.protobuf:
                self.health_proto.camera.CopyFrom(self.cam_proto)
                self.health_proto.check_result = False
                return self.health_proto.SerializeToString().decode("utf-8")
            return False
        if self.protobuf:
            self.health_proto.camera.CopyFrom(self.cam_proto)
            self.health_proto.check_result = bool(image)
            return self.health_proto.SerializeToString().decode("utf-8")
        else:
            return bool(image)

    def set_address(self, new_address):
        """Sets a new address (file path) for the camera.

        Args:
            new_address: The new file path to use as the camera source.

        Returns:
            bool: True if the address is set successfully, False otherwise.
        """
        self.close()
        self.image = None
        self.address = new_address
        self.open()


class RtspCamera(BasicCamera):
    """RTSP type camera class.

    Implements a camera class based on RTSP streaming.
    Uses OpenCV for interacting with the camera.

    Attributes:
      address: str
      user: str
      passwd: str
      device_id: str
      logger: logging.Logger
      stdout: str
      protobuf: bool
      cameras_list: list
      image: PIL.Image
      event: threading.Event
      cam_proto: cameras_pb2.Camera
      health_proto: cameras_pb2.CameraHealthCheckResult
      frame_proto: cameras_pb2.CameraFrameResult
      printout: bool
      capture: cv2.VideoCapture
      thread: threading.Thread
      last_return_code: bool
      last_frame: np.ndarray
      lock: threading.Lock
    """

    last_return_code = None
    last_frame = None
    lock = threading.Lock()

    def capture_frames(self, event, capture):
        """Consumes RTSP framebuffer so get_frame gets the latest frame.

        This method runs in a separate thread and continuously reads frames
        from the RTSP stream using the provided `cv2.VideoCapture` object.
        This ensures that the `get_frame` method always retrieves the most
        recent frame available.

        Args:
          event: A `threading.Event` object used to signal the thread to stop.
          capture: A `cv2.VideoCapture` object for the open RTSP stream.
        """
        while True:
            if event.is_set():
                break
            try:
                if capture.isOpened():
                    with self.lock:
                        self.last_return_code, self.last_frame = capture.read()
                        self.logger.debug("Read frame")
            except cv2.error:
                pass

    def __init__(
        self, address, user, passwd, device_id, logger, stdout, protobuf
    ):
        """Initializes with RTSP address and optional authentication.

        Args:
          address: RTSP address of the camera.
          user: Username for camera authentication (optional).
          passwd: Password for camera authentication (optional).
          device_id: Unique identifier for the camera instance.
          logger: Logger object for recording messages.
          stdout: Output mode for messages ('print' for stdout, 'protobuf'
            for protobuf messages).
          protobuf: Whether to use protobuf for output messages.
        """
        self.address = address
        self.user = user
        self.passwd = passwd
        self.device_id = device_id
        self.logger = logger
        self.stdout = stdout
        self.printout = self.stdout == "print"
        self.protobuf = protobuf
        self.cameras_list = []
        self.image = None
        self.event = threading.Event()
        self.cam_proto = cameras_pb2.Camera()
        self.health_proto = cameras_pb2.CameraHealthCheckResult()
        self.frame_proto = cameras_pb2.CameraFrameResult()

        if self.address:
            stream_proto = cameras_pb2.Camera.Stream()
            stream_proto.protocol = cameras_pb2.Camera.Stream.PROTOCOL_RTSP
            stream_proto.address = self.address
            self.cam_proto.streams.append(stream_proto)
            if user:
                if "@" not in address:
                    self.address = (
                        f"rtsp://{self.user}:{self.passwd}@"
                        f"{self.address.split('rtsp://')[1]}"
                    )

            self.logger.debug(self.cam_proto)
            if self.printout:
                print("Using RTSP camera: {}".format(self.address))
            try:
                self.capture = cv2.VideoCapture(self.address)
                self.thread = threading.Thread(
                    target=self.capture_frames, args=(self.event, self.capture)
                )
                self.thread.start()
            except cv2.error as e:
                if self.printout:
                    print(e)

    def open(self):
        """Checks if the OpenCV VideoCapture connection is open."""
        self.logger.debug("Opening RTSP camera connection")
        if not self.capture.isOpened():
            if self.printout:
                print("Cannot open camera")
            self.close()
            exit(1)

    def close(self):
        """Closes OpenCV VideoCapture."""
        self.logger.debug("Closing RTSP camera connection")
        if self.address:
            self.event.set()
            self.thread.join()
            if self.capture:
                self.capture.release()

    def get_frame(self):
        """Gets the latest frame from RTSP stream.

        Returns:
          PIL.Image: The latest frame from the RTSP stream as a PIL Image,
            or None if no frame is available.
          str: Protobuf string if protobuf is True, None otherwise.
        """
        self.logger.debug(
            "RTSP camera get_frame return code: {} data type: {}".format(
                self.last_return_code, type(self.last_frame)
            )
        )
        if not self.last_return_code:
            self.logger.debug("No frame received, looping")
            while not self.last_return_code:
                continue
        pil_image = Image.fromarray(
            cv2.cvtColor(self.last_frame, cv2.COLOR_BGR2RGB)
        )
        if not self.protobuf:
            return pil_image

        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        buf.seek(0)
        self.frame_proto.png_frame = buf.read()
        self.frame_proto.camera.CopyFrom(self.cam_proto)
        return self.frame_proto.SerializeToString().decode("utf-8")

    def health_check(self):
        """Checks if we can get valid frames from RTSP stream.

        Returns:
          bool: True if a valid frame can be retrieved, False otherwise.
          str: Protobuf string with health check result if protobuf is True,
            None otherwise.
        """
        self.logger.debug("RTSP camera health_check - trying to get an image")
        image = self.get_frame()
        if not image:
            if self.printout:
                print("Error reading frame from RTSP stream.")
                return False
            elif self.protobuf:
                self.health_proto.camera.CopyFrom(self.cam_proto)
                self.health_proto.check_result = False
                return self.health_proto.SerializeToString().decode("utf-8")
            else:
                return False
        if self.protobuf:
            self.health_proto.camera.CopyFrom(self.cam_proto)
            if not image:
                self.health_proto.check_result = False
            else:
                self.health_proto.check_result = True
            return self.health_proto.SerializeToString().decode("utf-8")
        else:
            if not image:
                return False
            else:
                return True


class OnvifCamera(RtspCamera):
    """ONVIF type RTSP camera class.

    Implements a camera class based on RTSP streaming,
    with additional ONVIF support on the camera. ONVIF
    adds configuration control and discovery of cameras,
    as well as their RTSP streams, for more advanced
    RTSP cameras.

    Attributes:
      discovery_proto: CameraDiscoveryResult proto
    """

    def _discovery_results(self, cameras_list):
        """Returns a cameras_pb2.CameraDiscoveryResult proto of addresses."""
        self.logger.debug(
            "ONVIF Camera _discovery_results. Cameras_list: {}".format(
                cameras_list
            )
        )
        discovery_proto = cameras_pb2.CameraDiscoveryResult()

        for cam in cameras_list:
            camera_proto = cameras_pb2.Camera()
            camera_proto.make = cam["make"]
            camera_proto.model = cam["model"]

            for stream in cam["streams"]:
                stream_proto = cameras_pb2.Camera.Stream()
                stream_proto.protocol = cameras_pb2.Camera.Stream.PROTOCOL_ONVIF
                stream_proto.address = stream

                camera_proto.streams.append(stream_proto)
            discovery_proto.cameras.append(camera_proto)
        return discovery_proto

    def __init__(
        self, address, user, passwd, device_id, logger, stdout, protobuf
    ):
        """Initializes the instance with base RTSP init, plus ONVIF scan.

        Args:
          address: RTSP address of the camera. If None, only ONVIF scans.
          user: Username for camera authentication (optional).
          passwd: Password for camera authentication (optional).
          device_id: Unique identifier for the camera instance.
          logger: Logger object for recording messages.
          stdout: Output mode for messages ('print' for stdout, 'protobuf'
            for protobuf messages).
          protobuf: Whether to use protobuf for output messages.
        """
        super().__init__(
            address, user, passwd, device_id, logger, stdout, protobuf
        )

        self.cameras_list = self.scan()

        if self.cameras_list:
            self.discovery_proto = self._discovery_results(self.cameras_list)
        else:
            self.discovery_proto = None

        if self.address:
            for cam in self.cameras_list:
                if self.address in cam["streams"]:
                    self.cam_proto.make = cam["make"]
                    self.cam_proto.model = cam["model"]
                    self.logger.debug(self.cam_proto)

        if self.printout and self.cameras_list:
            print("ONVIF cameras found:")
            for cam in self.cameras_list:
                print(
                    "Make: {} | Model: {} | Addresses: {}".format(
                        cam["make"], cam["model"], cam["streams"]
                    )
                )
        elif self.stdout == "protobuf" and not self.address:
            self.logger.debug("Printing scan results in protobuf")
            print_without_eol(
                self.discovery_proto.SerializeToString().decode("utf-8")
            )

    def scan(self):
        """Scans the LAN for ONVIF cameras and their RTSP streams.

        Returns:
          list: A list of dictionaries, where each dictionary represents a
            discovered ONVIF camera. The camera dictionary contains the
            keys 'make', 'model', and 'streams'. The 'streams' key contains
            a list of RTSP addresses for the camera. Returns None if no
            cameras are found.
        """
        scanned = []
        found = []

        ttype = wsdiscovery.QName(
            "http://www.onvif.org/ver10/network/wsdl", "NetworkVideoTransmitter"
        )
        scope = wsdiscovery.Scope("onvif://www.onvif.org/")

        warnings.filterwarnings(
            action="ignore", message="unclosed", category=ResourceWarning
        )
        if self.printout:
            print("Discovering ONVIF cameras on the network...")
        wsd = WSDiscovery()
        wsd.start()
        services = wsd.searchServices(types=[ttype], scopes=[scope])
        for service in services:
            uuid = service.getEPR().split(":")[2]
            parsed = urllib.parse.urlparse(service.getXAddrs()[0])
            addr, port = parsed.netloc.split(":")
            scanned.append({"uuid": uuid, "addr": addr, "port": port})
        wsd.stop()
        if scanned:
            wdsl_path = onvif.__path__[0].replace("onvif", "wsdl")
            if self.printout:
                print("ONVIF cameras found: {}".format(scanned))
                print("Querying found ONVIF cameras for RTSP URIs..")
            for scan in scanned:
                try:
                    self.logger.debug(scan)
                    cam = {}
                    mycam = onvif.ONVIFCamera(
                        scan["addr"],
                        scan["port"],
                        self.user,
                        self.passwd,
                        wdsl_path,
                    )
                    device_info = mycam.devicemgmt.GetDeviceInformation()
                    self.logger.debug(device_info)
                    cam["make"] = device_info["Manufacturer"]
                    cam["model"] = device_info["Model"]
                    cam["streams"] = []
                    media_service = mycam.create_media_service()
                    profiles = media_service.GetProfiles()
                    for profile in profiles:
                        token = profile.token
                        stream_uri = media_service.GetStreamUri(
                            {
                                "StreamSetup": {
                                    "Stream": "RTP-Unicast",
                                    "Transport": "UDP",
                                },
                                "ProfileToken": token,
                            }
                        )
                        rtsp_uri = stream_uri["Uri"]
                        cam["streams"].append(rtsp_uri)
                    found.append(cam)
                except onvif.ONVIFError as e:
                    if self.printout:
                        print("Error querying ONVIF camera: {}".format(e))
        else:
            if self.printout:
                print("No ONVIF cameras discovered")
            return None
        self.logger.debug(found)
        return found


class UsbCamera(ConfigurableCamera):
    """USB type camera class.

    Implements a camera class based on USB protocol.
    USB cameras are directly connected to the host USB bus.
    Uses OpenCV for interacting with the camera.

    Attributes:
      address: str.
      device_id: str.
      logger: logging.Logger.
      stdout: str.
      protobuf: bool.
      cameras_list: list.
      capture: cv2.VideoCapture.
      cam_proto: cameras_pb2.Camera.
      health_proto: cameras_pb2.CameraHealthCheckResult.
      frame_proto: cameras_pb2.CameraFrameResult.
      printout: bool.
      discovery_proto: cameras_pb2.CameraDiscoveryResult.
    """

    def _discovery_results(self, cameras_list):
        """Returns a cameras_pb2.CameraDiscoveryResult proto of addresses.

        Args:
          cameras_list: A list of dicts, where each dict represents a
            discovered ONVIF camera. The camera dict contains the
            keys 'make', 'model', and 'streams'. The 'streams' key contains
            a list of RTSP addresses for the camera.

        Returns:
          cameras_pb2.CameraDiscoveryResult: Protobuf message containing
            information about discovered cameras and their streams.
        """
        self.logger.debug(
            "USB Camera _discovery_results. Cameras_list: {}".format(
                cameras_list
            )
        )
        discovery_proto = cameras_pb2.CameraDiscoveryResult()

        for cam in cameras_list:
            camera_proto = cameras_pb2.Camera()
            camera_proto.make = cam["make"]
            camera_proto.model = cam["model"]

            stream_proto = cameras_pb2.Camera.Stream()
            stream_proto.protocol = cameras_pb2.Camera.Stream.PROTOCOL_USB
            stream_proto.address = cam["address"]

            camera_proto.streams.append(stream_proto)
            discovery_proto.cameras.append(camera_proto)
        return discovery_proto

    def __init__(self, address, device_id, logger, stdout, protobuf):
        """Initializes the instance with USB device address.

        Args:
          address: str, USB device address.
          device_id: str, Unique identifier for the camera instance.
          logger: logging.Logger, Logger object for recording messages.
          stdout: str, Output mode for messages ('print' for stdout, 'protobuf'
            for protobuf messages).
          protobuf: bool, Whether to use protobuf for output messages.
        """
        self.address = address
        self.device_id = device_id
        self.logger = logger
        self.stdout = stdout
        self.printout = self.stdout == "print"
        self.protobuf = protobuf
        self.cameras_list = []
        self.capture = None
        self.cam_proto = cameras_pb2.Camera()
        self.health_proto = cameras_pb2.CameraHealthCheckResult()
        self.frame_proto = cameras_pb2.CameraFrameResult()

        self.cameras_list = self.scan()
        self.discovery_proto = self._discovery_results(self.cameras_list)

        if self.printout:
            print("USB cameras found:")
            for cam in self.cameras_list:
                print(
                    "Address: {} | Model: {} | # of Properties: {}".format(
                        cam["address"], cam["model"], len(cam["properties"])
                    )
                )
        elif "protobuf" in self.stdout and not self.address:
            self.logger.debug("Printing scan results in protobuf")
            print_without_eol(
                self.discovery_proto.SerializeToString().decode("utf-8")
            )

        if self.address:
            stream_proto = cameras_pb2.Camera.Stream()
            stream_proto.protocol = cameras_pb2.Camera.Stream.PROTOCOL_USB
            stream_proto.address = self.address
            self.cam_proto.streams.append(stream_proto)
            for cam in self.cameras_list:
                if self.address == cam["address"]:
                    self.cam_proto.make = cam["make"]
                    self.cam_proto.model = cam["model"]
            self.logger.debug(
                "Opening capture connection to: {}".format(self.address)
            )
            self.capture = cv2.VideoCapture(self.address)
            self.logger.debug(self.cam_proto)

    def open(self):
        """Checks if VideoCapture is open to the camera."""
        if not self.capture.isOpened():
            if self.printout:
                self.logger.error("Cannot open camera")
            exit(1)

    def close(self):
        """Closes VideoCapture."""
        if self.capture:
            self.capture.release()

    def get_frame(self):
        """Gets a frame from the camera."""
        return_value, frame = self.capture.read()
        if not return_value:
            return None

        pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if not self.protobuf:
            return pil_image

        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        buf.seek(0)
        self.frame_proto.png_frame = buf.read()
        self.frame_proto.camera.CopyFrom(self.cam_proto)
        return self.frame_proto.SerializeToString().decode("utf-8")

    def get_property(self, key):
        """Gets a configuration parameter's value from the camera.

        Args:
          key: str, The name of the configuration parameter to retrieve.

        Returns:
          The value of the configuration parameter, or None if an error occurs.
        """
        try:
            value = self.capture.get(getattr(cv2, key))
        except cv2.error:
            return None
        else:
            return value

    def set_property(self, key, value):
        """Sets a configuration parameter's value on the camera."""
        try:
            self.capture.set(getattr(cv2, key), value)
        except cv2.error:
            if self.printout:
                print(
                    "Failed to write camera configuration parameter: {}".format(
                        key
                    )
                )

    def get_properties(self):
        """Gets all configurations from the camera.

        Returns:
          dict: A dictionary containing the camera's configuration parameters
            and their values.
        """
        props = {}
        all_props = dir(cv2)
        for prop in all_props:
            if "CAP_PROP" in prop:
                props[prop] = self.get_property(prop)
        return props

    def set_properties(self, configs):
        """Sets all configurations from the camera.

        Args:
          configs: dict, A dictionary containing the camera's configuration
            parameters and their desired values.
        """
        for key in configs:
            if self.printout:
                print(
                    "Writing config to the camera: {} = {}".format(
                        key, configs[key]
                    )
                )
            self.set_property(key, configs[key])

    def scan(self):
        """Scans the local server USB bus for connected cameras.

        Returns:
          list: A list of dictionaries, where each dictionary represents a
            discovered USB camera. The camera dictionary contains the
            keys 'address', 'make', 'model', and 'properties'. Returns
            None if no cameras are found.
        """
        found = []
        warnings.filterwarnings(action="ignore")
        if self.printout:
            print("Discovering USB cameras...")
        devs = os.listdir("/dev/")
        for dev in devs:
            if "video" in dev:
                cam_name_path = "/sys/class/video4linux/" + dev + "/name"
                dev = "/dev/" + dev
                capture = cv2.VideoCapture(dev)
                if capture.isOpened():
                    cam = {}
                    cam["address"] = dev
                    props = self.get_properties()
                    if props:
                        cam["properties"] = props
                    try:
                        f = open(cam_name_path, "r", encoding="utf-8")
                    except cv2.error as e:
                        self.logger.debug(
                            "Cannot open file %s for reading: %s",
                            cam_name_path,
                            e,
                        )
                    name = f.read()
                    name = name.strip()
                    cam["make"] = name
                    cam["model"] = name
                    found.append(cam)
                    capture.release()
                    f.close()
        self.logger.debug("cameras_list: {}".format(found))
        return found

    def health_check(self):
        """Checks if we can get a valid frame from the camera."""
        image = self.get_frame()
        if not image:
            if self.printout:
                print("Error reading frame from camera.")
                return False
            elif self.protobuf:
                self.health_proto.camera.CopyFrom(self.cam_proto)
                self.health_proto.check_result = False
                return self.health_proto.SerializeToString().decode("utf-8")
            else:
                return False
        if self.protobuf:
            self.health_proto.camera.CopyFrom(self.cam_proto)
            if not image:
                self.health_proto.check_result = False
            else:
                self.health_proto.check_result = True
            return self.health_proto.SerializeToString().decode("utf-8")
        else:
            if not image:
                return False
            else:
                return True


class GenicamCamera(ConfigurableCamera):
    """Genicam type camera class.

    Implements a camera class based on Genicam/GigE Vision
    protocol. Genicam cameras support discovery and config
    control. Implemented using harvesters Genicam module.

    Attributes:
      address: str.
      device_id: str.
      gentl: str.
      logger: logging.Logger.
      stdout: str.
      protobuf: bool.
      cameras_list: list.
      img_acquirer: harvesters.core.ImageAcquirer.
      cam_proto: cameras_pb2.Camera.
      health_proto: cameras_pb2.CameraHealthCheckResult.
      frame_proto: cameras_pb2.CameraFrameResult.
      printout: bool.
      harvester: harvesters.core.Harvester.
      discovery_proto: cameras_pb2.CameraDiscoveryResult.
    """

    def _discovery_results(self, cameras_list):
        """Returns a cameras_pb2.CameraDiscoveryResult proto of addresses.

        Returns:
          cameras_pb2.CameraDiscoveryResult: Protobuf message containing
            information about discovered cameras and their addresses.
        """
        self.logger.debug(
            "Genicam Camera _discovery_results. Cameras_list: {}".format(
                cameras_list
            )
        )
        discovery_proto = cameras_pb2.CameraDiscoveryResult()

        for cam in cameras_list:
            camera_proto = cameras_pb2.Camera()
            camera_proto.make = cam["make"]
            camera_proto.model = cam["model"]

            stream_proto = cameras_pb2.Camera.Stream()
            stream_proto.protocol = cameras_pb2.Camera.Stream.PROTOCOL_GENICAM
            stream_proto.address = cam["address"]

            camera_proto.streams.append(stream_proto)
            discovery_proto.cameras.append(camera_proto)
        return discovery_proto

    def __init__(self, address, device_id, gentl, logger, stdout, protobuf):
        """Initializes the instance with Genicam address, from 0 onwards.

        Args:
          address: str, Genicam device address, from 0 onwards.
          device_id: str, Unique identifier for the camera instance.
          gentl: str, Path to the GenTL producer file.
          logger: logging.Logger, Logger object for recording messages.
          stdout: str, Output mode for messages ('print' for stdout, 'protobuf'
            for protobuf messages).
          protobuf: bool, Whether to use protobuf for output messages.
        """
        self.address = address
        self.device_id = device_id
        self.gentl = gentl
        self.logger = logger
        self.stdout = stdout
        self.printout = self.stdout == "print"
        self.protobuf = protobuf
        self.cameras_list = []
        self.img_acquirer = None
        self.cam_proto = cameras_pb2.Camera()
        self.health_proto = cameras_pb2.CameraHealthCheckResult()
        self.frame_proto = cameras_pb2.CameraFrameResult()
        self.harvester = Harvester(logger=logger)
        self.harvester.add_file(gentl)
        self.harvester.timeout_for_update = 5000
        self.cameras_list = self.scan()
        self.discovery_proto = self._discovery_results(self.cameras_list)

        if self.printout:
            print("Genicam cameras found:")
            for cam in self.cameras_list:
                print(
                    "Address: {} | Make: {} | Model: {}".format(
                        cam["address"], cam["make"], cam["model"]
                    )
                )
        elif "protobuf" in self.stdout:
            self.logger.debug("Printing scan results in protobuf")
            print_without_eol(
                self.discovery_proto.SerializeToString().decode("utf-8")
            )

        if self.address:
            stream_proto = cameras_pb2.Camera.Stream()
            stream_proto.protocol = cameras_pb2.Camera.Stream.PROTOCOL_GENICAM
            stream_proto.address = self.address
            self.cam_proto.streams.append(stream_proto)
            for cam in self.cameras_list:
                if self.address == cam["address"]:
                    self.cam_proto.make = cam["make"]
                    self.cam_proto.model = cam["model"]
            self.logger.debug(
                "Opening capture connection to: {}".format(self.address)
            )
            self.img_acquirer = self.harvester.create(
                search_key=int(self.address)
            )
            self.img_acquirer.start(run_as_thread=True)
            self.logger.debug(self.cam_proto)

    def open(self):
        """Checks if the harvesters Image Acquirer is working normally."""
        if self.printout:
            print(
                "Image Acquirer status: valid:{} armed:{} acquiring:{}".format(
                    self.img_acquirer.is_valid(),
                    self.img_acquirer.is_armed(),
                    self.img_acquirer.is_acquiring(),
                )
            )

    def close(self):
        """Closes the harvesters Image Acquirer."""
        if self.img_acquirer:
            self.img_acquirer.stop()
            self.harvester.reset()

    def get_frame(self, args, one_d, height, width):
        """Gets a sensor array dump from the camera and pre-processes.

        Args:
          args: program arguments.
          one_d: one dimensional array.
          height: image height.
          width: image width.

        Returns:
          PIL.Image: pre-processed image frame.
          self.frame_proto: protobuf frame.
        """
        if not height:
            one_d, height, width, _ = self.get_raw()
            if not height:
                if self.printout:
                    print("Genicam image acquiry failed")
                return None
        two_d = one_d.reshape(height, width)

        if args.range_max == 0:
            two_d_bits = np.interp(two_d, (two_d.min(), two_d.max()), (0, 254))
        else:
            two_d_bits = np.interp(
                two_d, (args.range_min, args.range_max), (0, 254)
            )

        if args.mode != "continuous" and self.printout:
            print(
                "Mapping from raw to 8bit: min: {}->{}, max: {}->{}".format(
                    two_d.min(), two_d_bits.min(), two_d.max(), two_d_bits.max()
                )
            )
        pil_image = Image.fromarray(
            two_d_bits.astype(np.uint8), mode="L"
        ).convert("RGB")
        if not self.protobuf:
            return pil_image

        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        buf.seek(0)
        self.frame_proto.png_frame = buf.read()
        self.frame_proto.camera.CopyFrom(self.cam_proto)
        return self.frame_proto.SerializeToString().decode("utf-8")

    def get_property(self, n):
        """Gets a configuration parameter's value from the camera.

        Args:
          n: str, The name of the configuration parameter to retrieve.

        Returns:
          The value of the configuration parameter, or None if an error occurs.
        """
        try:
            value = getattr(self.img_acquirer.remote_device.node_map, n).value
        except AttributeError:
            return None
        except TypeError:
            return None
        return value

    def set_property(self, key, value):
        """Sets a configuration parameter's value to the camera."""
        try:
            setattr(self.img_acquirer.remote_device.node_map, key, value)
        except AttributeError:
            if self.printout:
                print(
                    "Failed to write camera configuration parameter: {}".format(
                        key
                    )
                )
        except TypeError:
            if self.printout:
                print(
                    "Failed to write camera configuration parameter: {}".format(
                        key
                    )
                )
        except ValueError:
            if self.printout:
                print(
                    "Failed to write camera configuration parameter: {}".format(
                        key
                    )
                )

    def get_properties(self):
        """Gets all configurations from the camera.

        Returns:
          dict: A dictionary containing the camera's configuration parameters
            and their values.
        """
        props = {}
        node_map = dir(self.img_acquirer.remote_device.node_map)
        for node in node_map:
            if "__" not in node:
                value = self.get_property(node)
                if value:
                    if isinstance(value, str):
                        props[node] = '"' + value + '"'
                    else:
                        props[node] = value
        return props

    def set_properties(self, configs):
        """Sets all configurations on the camera.

        Args:
          configs: dict, A dictionary containing the camera's configuration
            parameters and their desired values.
        """
        for key in configs:
            if self.printout:
                print(
                    "Writing config to the camera: {} = {}".format(
                        key, configs[key]
                    )
                )
            self.set_property(key, configs[key])

    def scan(self):
        """Scans the LAN for Genicam/GigE Vision cameras."""
        found = []
        if self.printout:
            print("Discovering Genicam cameras on the network...")
        self.harvester.update()

        for i in range(len(self.harvester.device_info_list)):
            device = self.harvester.device_info_list[i]
            device_dict = device.property_dict
            cam = {}
            cam["address"] = str(i)
            cam["properties"] = {}
            cam["make"] = device_dict["vendor"]
            cam["model"] = device_dict["model"]
            found.append(cam)
        self.logger.debug("cameras_list: {}".format(found))
        return found

    def get_raw(self):
        """Gets a raw sensor array dump from the e.g Thermal camera.

        Returns:
          tuple: A tuple containing the raw sensor data, height, width,
            and buffer object. Returns None if no data is available.
        """
        buffer = self.img_acquirer.try_fetch(timeout=3)
        if buffer:
            component = buffer.payload.components[0]
            return (component.data, component.height, component.width, buffer)
        else:
            return

    def queue(self, buffer):
        """Queues the Genicam frames receive buffer."""
        buffer.queue()

    def health_check(self):
        """Checks if we can get data from the camera.

        Returns:
          bool: True if data can be retrieved, False otherwise.
          str: Protobuf  containing health check result if protobuf is True,
            None otherwise.
        """
        _, harvester, _, _ = self.get_raw()
        if not harvester:
            if self.printout:
                print("Error reading data from camera.")
                return False
            elif self.protobuf:
                self.health_proto.camera.CopyFrom(self.cam_proto)
                self.health_proto.check_result = False
                return self.health_proto.SerializeToString().decode("utf-8")
            else:
                return False
        if self.protobuf:
            self.health_proto.camera.CopyFrom(self.cam_proto)
            if not harvester:
                self.health_proto.check_result = False
            else:
                self.health_proto.check_result = True
            return self.health_proto.SerializeToString().decode("utf-8")
        else:
            if not harvester:
                return False
            else:
                return True
