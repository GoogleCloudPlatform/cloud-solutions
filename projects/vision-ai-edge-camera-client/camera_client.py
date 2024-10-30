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

# pylint: disable=E1120
# ruff: noqa

"""Camera client utility.

Lets users connect to cameras with different protocols,
configure the cameras and acquire data from them,
run ML inference against the camera frames,
forward the results to Google Cloud and expose them via MQTT.

Typical usage example:

  python3 camera_client.py --protocol usb --address /dev/video0
  --device_id usbcam1 --img_write --mode interactive
"""

import argparse
import base64
import configparser
import datetime
import io
import json
import logging
import os
import time
import warnings

import construct
import numpy as np
import paho.mqtt.client as mqtt
import puremagic
import requests
from google.api_core.gapic_v1 import client_info
from google.cloud import pubsub_v1
from rfc3339 import rfc3339

import edge_camera

_SOLUTION_USER_AGENT = "cloud-solutions/vision-ai-edge-camera-client-v1"

warnings.filterwarnings("ignore", category=DeprecationWarning)

mqtt_msg = None
mqtt_topic = None


def transmit_mqtt(printout, logger, mqtt_client, results, topic):
    """Transmits ML result to local MQTT topic.

    Uses MQTT paho client to transmit ML results to a local network MQTT topic.

    Args:
      printout: printing messages to stdout.
      logger: main logger client.
      mqtt_client: local network MQTT connection client.
      results: ML inference results from VIAI model.
    """
    if printout:
        logger.info("Transmitting ML inference results to local MQTT")
    mqtt_client.publish(topic, json.dumps(results))
    if printout:
        logger.info("Local MQTT transmit complete")


def transmit_pubsub(printout, logger, publisher, args, data):
    """Transmits payload to Cloud Pub/Sub.

    Transmits a payload to Cloud Pub/Sub. Either image or ML results.
    Cloud project and Pub/Sub topic from args.

    Args:
      printout: printing messages to stdout.
      logger: main logger client.
      publisher: Pub/Sub client.
      args: main program command line arguments.
      data: payload to transmit.
    """
    if printout:
        logger.info("Transmitting data to Cloud Pub/Sub")
    topic = "projects/{}/topics/{}".format(args.project_id, args.topic_id)
    if "image" in args.pubsub:
        img_byte_arr = io.BytesIO()
        data.save(img_byte_arr, format="PNG")
        data = img_byte_arr.getvalue()
    future = publisher.publish(topic, data, type=args.pubsub)
    if printout:
        logger.info(future.result())
        logger.info("Published data to Pub/Sub topic {}".format(topic))


def read_config(printout, logger, cam, cfg_file):
    """Queries camera for its runtime configurations and save to file.

    For camera types that support configuration management, uses the cam
    class get_properties() method, to query camera's current configs.
    Writes config parameter/value pairs to an output text file.

    Args:
      printout: printing messages to stdout.
      logger: main logger client.
      cam: camera object.
      cfg_file: queried configurations output file.
    """
    if printout:
        logger.info("Querying camera runtime cfg and saving to: %s", cfg_file)
    props = cam.get_properties()
    logger.debug("Camera properties: {}".format(props))

    with open(cfg_file, "w", encoding="utf-8") as f:
        for prop in props.keys():
            f.write("{} = {}\n".format(prop, props[prop]))
    f.close()


def create_pubsub_payload(results, logger):
    """Creates a binary payload compatible with Cloud Pub/Sub.

    Receives a dict containing ML inference results, or a thermal
    camera pre-processed data dict. For ML results, creates a JSON dump,
    for thermal data, uses Python construct to create a
    custom binary payload.

    Args:
      results: payload dict.
      logger: Logging component.

    Returns:
      payload or None, if input data format not recognized.
    """
    if "results" in results.keys():
        return json.dumps(results).encode("utf-8")

    elif "temp_array" in results.keys():
        payload_struct = construct.Struct(
            "device_id" / construct.PascalString(construct.VarInt, "utf-8"),
            "ts" / construct.PascalString(construct.VarInt, "utf-8"),
            "temp_format" / construct.PascalString(construct.VarInt, "utf-8"),
            "temp_avg" / construct.Half,
            "temp_min" / construct.Half,
            "temp_max" / construct.Half,
            "temp_array" / construct.GreedyRange(construct.Short),
        )

        payload = payload_struct.build(
            dict(
                device_id=results["device_id"],
                ts=results["ts"],
                temp_format=results["temp_format"],
                temp_avg=results["temp_avg"],
                temp_min=results["temp_min"],
                temp_max=results["temp_max"],
                temp_array=results["temp_array"],
            )
        )
        return payload
    else:
        logger.error("Unknown input data format")
        return


def write_config(printout, logger, cam, cfg_file):
    """Write desired configurations to the camera.

    For camera types that support configuration management, uses the cam
    class set_properties() method, to write or update the camera's
    runtime configs. Read config parameter/value pairs from input text file.

    Args:
      printout: printing messages to stdout.
      logger: main logger client.
      cam: camera object.
      cfg_file: target configurations input file.
    """
    if printout:
        logger.info("Reading config file: {}".format(cfg_file))
    try:
        f = open(cfg_file, "r", encoding="utf-8")
    except IOError:
        if printout:
            logger.error("Error reading file")
        exit(1)
    configs = {}
    for row in f:
        key, value = row.split(" = ")
        value = value.rstrip()
        if value == "True":
            configs[key] = True
        elif value == "False":
            configs[key] = False
        elif '"' in value:
            configs[key] = str(value).replace('"', "")
        elif "." in value or "e" in value:
            configs[key] = float(value)
        else:
            configs[key] = int(value)
    f.close()

    logger.debug("Writing configs to camera: {}".format(configs))

    cam.set_properties(configs)
    return


def exit_gracefully(cam, mqtt_client):
    """Closes camera and MQTT connections and exits gracefully.

    Closes all connections gracefully and exits with code 0.

    Args:
      cam: camera object.
      mqtt_client: local network MQTT client.
    """
    cam.close()
    if mqtt_client:
        mqtt_client.loop_stop()
    exit(0)


def int_map_range(x, in_min, in_max, out_min, out_max):
    """Maps an input value from one value range to another, as int.

    Used for thermal data pre-processing, for example to change
    microbolometer values from 14-bit float accuracy to 8-bit int.

    Args:
      x: input value.
      in_min: input value range min.
      in_max: input value range max.
      out_min: new value range min.
      out_max: new value range max.

    Returns:
      int of the input value, in the new value range.
    """
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)


def create_request_body(image_data, request_body_template):
    """Creates the request body to perform API calls.

    Args:
        image_data: The input image.
        request_body_template (str): Bbody template with placeholders.

    Returns:
        A JSON format string of the request body.
    """
    encoded_string = base64.b64encode(image_data).decode("utf-8")

    # Use json.loads to parse the template string into a Python dictionary
    request_body = json.loads(request_body_template)

    # Define a recursive function to find and replace the placeholder
    def replace_placeholder(data):
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and "{encoded_string}" in value:
                    data[key] = value.format(encoded_string=encoded_string)
                else:
                    replace_placeholder(value)
        elif isinstance(data, list):
            for _, item in enumerate(data):
                replace_placeholder(item)

    # Call the recursive function to replace the placeholder
    replace_placeholder(request_body)

    return json.dumps(request_body)


def predict(printout, logger, image_data, ml_url, request_body_template):
    """Predict results on the input image using services at the given port.

    Args:
        printout: printing messages to stdout.
        logger: main logger client.
        image_data: The input image.
        ml_url: The URL of the ML model service.
        request_body_template: The request body template with placeholders.

    Returns:
      The predicted results in JSON format or None.
    """
    url = ml_url
    request_body = create_request_body(image_data, request_body_template)
    logger.debug(f"Sending image to ML URL: {url}")

    try:
        response = requests.post(url, data=request_body)
        logger.debug("Response received: {}".format(response))
    except requests.exceptions.RequestException as e:
        if printout:
            logger.error(
                "Error posting image to model service port: %s", format(e)
            )
        return

    json_response = ""
    try:
        json_response = response.json()
    except requests.exceptions.JSONDecodeError:
        if printout:
            logger.error("ML response not in JSON format: %s", response.text())
    return json_response


def mqtt_on_connect(client, userdata, unused_arg2, rc):
    """Subscribes to the MQTT topic.

    MQTT connect callback. Subscribes to the topic, after the
    MQTT broker connection has been opened.

    Args:
      client: MQTT client.
      userdata: MQTT userdata, contains topic to subscribe to.
      unused_arg2: MQTT flags, not used.
      rc: MQTT return code, not used.
    """
    print(f"Local network MQTT connected with result code {rc}")
    print(f"Subscribing to MQTT topic: {userdata}/#")
    ret = client.subscribe(userdata + "/#", qos=0)
    print(f"MQTT subscription result code: {ret}")


def mqtt_on_message(unused_arg1, unused_arg2, msg):
    """Receives an MQTT message.

    MQTT message received callback. Updates a global variable
    with the received data payload. The MQTT client runs in
    a separate thread, thus global variable used to make the
    payload visible to the main function.

    Args:
      unused_arg1: MQTT client, not used.
      unused_arg2: MQTT userdata, not used.
      msg: received message.
    """
    global mqtt_msg
    mqtt_msg = msg.payload.decode("utf-8")

    global mqtt_topic
    mqtt_topic = msg.topic


def process_files(directory):
    """Recursively searches a directory for image files and returns a list
    of their paths.

    Args:
      directory: The directory to search.

    Returns:
      A list of full paths to image files within the directory and its
      subdirectories.
    """
    batch_files = []

    for file in os.listdir(directory):
        full_path = os.path.join(directory, file)
        if os.path.isdir(full_path):
            process_files(full_path)
        else:
            image_type = puremagic.magic.from_file(full_path)
            if image_type is not None:
                batch_files.append(full_path)
    return batch_files


def load_client_config(config_file):
    """Loads the app configuration from specified file.

    Args:
        config_file (str): Path to the configuration file.
    """
    client_config = configparser.ConfigParser()
    client_config.read(config_file)
    return client_config


def parse_args():
    """Parses arguments.

    Returns:
      Parsed arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log",
        default="warning",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Provide logging level. Example --log debug, default=warning",
    )
    parser.add_argument(
        "--protocol",
        default="genicam",
        choices=["genicam", "onvif", "rtsp", "usb", "file"],
        help="Camera or image source connectivity method",
    )
    parser.add_argument("--device_id", help="Camera ID string", default="1")
    parser.add_argument(
        "--address",
        default=None,
        type=str,
        help="Camera address to connect to. For Genicam, integer from 0-n",
    )
    parser.add_argument(
        "--cam_user", default="", type=str, help="Camera access username"
    )
    parser.add_argument(
        "--cam_passwd", default="", type=str, help="Camera access password"
    )
    parser.add_argument(
        "--gentl",
        default="GenTL/FLIR_GenTL_Ubuntu_20_04_x86_64.cti",
        type=str,
        help="Camera Gen_TL file path",
    )
    parser.add_argument(
        "--background_acquisition",
        help="True: GenTL background acquisition. False: Buffer from camera",
        default=True,
        type=bool,
    )
    parser.add_argument(
        "--mode",
        default="none",
        choices=[
            "none",
            "single",
            "continuous",
            "interactive",
            "mqtt_sub",
            "batch",
        ],
        help="Imaging acquisition mode. None for camera config read or write",
    )
    parser.add_argument(
        "--width",
        default=0,
        type=int,
        help="Image width in pixels. Resized to this value if needed.",
    )
    parser.add_argument(
        "--height",
        default=0,
        type=int,
        help="Image height in pixels. Resized to this value if needed.",
    )
    parser.add_argument(
        "--count",
        default=0,
        type=int,
        help="Number of images to generate. 0 for indefinite.",
    )
    parser.add_argument(
        "--sleep",
        type=int,
        default=0,
        help="Sleep interval in seconds between loops. Default: 0",
    )
    parser.add_argument(
        "--pubsub",
        default="none",
        choices=["none", "results"],
        help="Whether to transmit ML inference results or none to Pub/Sub",
    )
    parser.add_argument(
        "--topic_id",
        default="camera-integration-telemetry",
        help="GCP Pub/Sub topic name",
    )
    parser.add_argument(
        "--ml",
        action="store_true",
        help="Whether to run ML inference on image feed",
    )
    parser.add_argument(
        "--raw_write",
        action="store_true",
        help="Whether to save raw IR sensor array data",
    )
    parser.add_argument(
        "--raw_write_path",
        default="raw/",
        help="Path where to write binary IR sensor array files",
    )
    parser.add_argument(
        "--img_write", action="store_true", help="Whether to save IR images"
    )
    parser.add_argument(
        "--img_write_path",
        default="images/",
        help="Path where to write IR image files",
    )
    parser.add_argument(
        "--cfg_read",
        action="store_true",
        help="Whether to read camera runtime configs and output to a file",
    )
    parser.add_argument(
        "--cfg_read_file",
        default="camera.cfg",
        help="Name of configuration file to output",
    )
    parser.add_argument(
        "--cfg_write",
        action="store_true",
        help="Whether to write user-defined configs from a file to the camera ",
    )
    parser.add_argument(
        "--cfg_write_file",
        help="Name of user-defined configuration file to apply",
    )
    parser.add_argument(
        "--temp_format",
        default="C",
        choices=["K", "C", "F"],
        help="Radiometric temperature format: K, C or F",
    )
    parser.add_argument(
        "--range_min",
        default=0,
        type=int,
        help="Raw data value to map to 8bit (0-254)",
    )
    parser.add_argument(
        "--range_max",
        default=0,
        type=int,
        help="Raw data value to map to 8bit (0-254)",
    )
    parser.add_argument(
        "--cloud_region", default="us-central1", help="GCP cloud region"
    )
    parser.add_argument("--project_id", help="GCP cloud project ID")
    parser.add_argument(
        "--credentials",
        default="./credentials.json",
        type=str,
        help="Service account JSON key. Default: ./credentials.json",
    )
    parser.add_argument(
        "--ml_host",
        default="127.0.0.1",
        type=str,
        help="IP address where the ML model inference service is running",
    )
    parser.add_argument(
        "--ml_port", default=8602, type=int, help="ML inference service port"
    )
    parser.add_argument(
        "--ml_write",
        action="store_true",
        help="Whether to save ML inference results JSON files",
    )
    parser.add_argument(
        "--ml_write_path",
        default="output/",
        help="Path where to write ML inference result JSON files",
    )
    parser.add_argument(
        "--mqtt",
        action="store_true",
        help="Whether to publish ML results to a local MQTT broker",
    )
    parser.add_argument(
        "--mqtt_host",
        default="localhost",
        type=str,
        help="Local network MQTT connection host address",
    )
    parser.add_argument(
        "--mqtt_port",
        default=1883,
        type=int,
        help="Local network MQTT connection host address",
    )
    parser.add_argument(
        "--mqtt_topic_commands",
        default="viai/commands",
        type=str,
        help="MQTT topic where to listen to commends",
    )
    parser.add_argument(
        "--mqtt_topic_results",
        default="viai/results",
        type=str,
        help="MQTT topic where to post ML results",
    )
    parser.add_argument(
        "--health_check",
        action="store_true",
        help="Test camera connection health. Exits with True|False",
    )
    parser.add_argument(
        "--stdout",
        default="print",
        choices=["none", "print", "protobuf"],
        help="STDOUT mode: none, print or protobuf",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="If enabled, scan for cameras of type --protocol only.",
    )
    parser.add_argument(
        "--stream_delay",
        type=int,
        help="Delay in ms before taking frame, to sync with stream latency.",
    )
    parser.add_argument(
        "--crop_left",
        default=-1,
        type=int,
        help="Crop coordinates left edge pixel.",
    )
    parser.add_argument(
        "--crop_top",
        default=-1,
        type=int,
        help="Crop coordinates top edge pixel.",
    )
    parser.add_argument(
        "--crop_right",
        default=-1,
        type=int,
        help="Crop coordinates right edge pixel.",
    )
    parser.add_argument(
        "--crop_bottom",
        default=-1,
        type=int,
        help="Crop coordinates bottom edge pixel.",
    )
    parser.add_argument(
        "--client_cfg_file",
        default=None,
        type=str,
        help="Name of configuration file to output",
    )
    return parser.parse_args()


def main():
    """Runs ML inference against camera images."""
    global mqtt_msg

    args = parse_args()

    client_config = {}
    logger = logging.getLogger()
    logger.setLevel(args.log.upper())
    streamhandler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    streamhandler.setFormatter(formatter)
    logger.addHandler(streamhandler)
    logger.debug("Main started")

    mqtt_client = None
    cwd = os.path.dirname(os.path.abspath("camera-client.py"))

    payload_struct_thermal = {}
    payload_struct_thermal["device_id"] = args.device_id
    payload_struct_thermal["temp_format"] = args.temp_format

    payload_struct = {}
    payload_struct["device_id"] = args.device_id

    printout = False
    if "print" in args.stdout:
        printout = True

    if args.client_cfg_file:
        if printout:
            logger.info("Loading client config from: %s", args.client_cfg_file)
        client_config = load_client_config(args.client_cfg_file)
        logger.debug("Client config: %s", client_config)

    if args.ml:
        try:
            url_template = client_config["ML_MODEL"].get("url")
            request_body_template = client_config["ML_MODEL"].get(
                "request_body"
            )
        except KeyError:
            if printout:
                logger.error(
                    "ML_MODEL section missing in cfg: %s. Exiting.",
                    args.client_cfg_file,
                )
                exit(1)
        if not url_template or not request_body_template:
            if printout:
                logger.error(
                    "ML_MODEL missing in cfg file: %s. Exiting.",
                    args.client_cfg_file,
                )
                exit(1)
        ml_url = url_template.format(hostname=args.ml_host, port=args.ml_port)
        if printout:
            logger.info("ML URL: %s", ml_url)
            logger.info("ML payload template: %s", request_body_template)

    protobuf = False
    if "protobuf" in args.stdout:
        protobuf = True

    crop = False
    if (
        args.crop_top > -1
        and args.crop_bottom > -1
        and args.crop_left > -1
        and args.crop_right > -1
    ):
        crop = True

    cam = None
    if args.protocol == "genicam":
        cam = edge_camera.GenicamCamera(
            args.address,
            args.device_id,
            os.path.join(cwd, args.gentl),
            logger,
            args.stdout,
            protobuf,
        )
    elif args.protocol == "onvif":
        cam = edge_camera.OnvifCamera(
            args.address,
            args.cam_user,
            args.cam_passwd,
            args.device_id,
            logger,
            args.stdout,
            protobuf,
        )
    elif args.protocol == "rtsp":
        cam = edge_camera.RtspCamera(
            args.address,
            args.cam_user,
            args.cam_passwd,
            args.device_id,
            logger,
            args.stdout,
            protobuf,
        )
    elif args.protocol == "usb":
        cam = edge_camera.UsbCamera(
            args.address, args.device_id, logger, args.stdout, protobuf
        )
    elif args.protocol == "file" and args.mode != "batch":
        cam = edge_camera.FileCamera(
            args.address, args.device_id, logger, args.stdout, protobuf
        )
    elif args.protocol == "file" and args.mode == "batch":
        pass
    else:
        if printout:
            logger.info("Unsupported protocol: %s. Exiting", args.protocol)
        exit(1)

    if args.scan:
        exit_gracefully(cam, mqtt_client)

    if args.health_check:
        cam.open()
        health = cam.health_check()
        if printout:
            logger.info("Camera health check result: %s", health)
        elif protobuf:
            edge_camera.print_without_eol(health)
        cam.close()
        exit(0)

    if args.cfg_write:
        if hasattr(cam, "set_properties"):
            write_config(printout, logger, cam, args.cfg_write_file)
        else:
            if printout:
                logger.info(
                    "Camera type: %s does not support cfg, exiting",
                    args.protocol,
                )
            exit(1)

    if args.cfg_read:
        if hasattr(cam, "get_properties"):
            read_config(printout, logger, cam, args.cfg_read_file)
        else:
            if printout:
                logger.info(
                    "Camera type: %s does not support cfg, exiting",
                    args.protocol,
                )
            exit(1)

    if args.img_write and args.mode != "none" and printout:
        logger.info("Saving images to: %s", args.img_write_path)

    if args.raw_write and args.mode != "none" and printout:
        logger.info("Saving raw data to: %s", args.raw_write_path)

    if args.ml and args.mode != "none" and printout:
        logger.info("Passing camera images to the ML model container")
        if args.ml_write:
            logger.info(
                "Writing inference result JSON files to: %s", args.ml_write_path
            )

    if args.mqtt:
        if printout:
            logger.info(
                "Starting MQTT client. Publishing results to: %s",
                args.mqtt_topic_results,
            )
        mqtt_client = mqtt.Client(userdata=args.mqtt_topic_commands)
        mqtt_client.on_connect = mqtt_on_connect
        mqtt_client.on_message = mqtt_on_message
        mqtt_client.connect_async(args.mqtt_host, args.mqtt_port, 60)
        mqtt_client.loop_start()

    if "none" not in args.pubsub:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = args.credentials
        publisher = pubsub_v1.PublisherClient(
            client_info=client_info.ClientInfo(user_agent=_SOLUTION_USER_AGENT)
        )
        publisher.topic_path(args.project_id, args.topic_id)
        if printout:
            logger.info("Created Pub/Sub client")

    byte_io = io.BytesIO()
    loop = False
    single = False
    interactive = False
    continuous = False
    mqtt_sub = False
    batch = False
    buffer = None
    sensor_array = None
    height = None
    width = None
    if args.mode != "none":
        loop = True
    if args.mode == "single":
        single = True
    elif args.mode == "interactive":
        interactive = True
    elif args.mode == "continuous":
        continuous = True
    elif args.mode == "mqtt_sub":
        mqtt_sub = True
    elif args.mode == "batch":
        batch = True

    count = 0
    total_count = args.count

    if batch:
        batch_files = process_files(args.address)
        total_count = len(batch_files)
        logger.debug("Batch input file list: %s: %s", total_count, batch_files)

    my_mqtt_topics = [
        args.mqtt_topic_commands,
        f"{args.mqtt_topic_commands}/{args.device_id}",
    ]
    if printout:
        logger.info("Listening to commands on MQTT topics: %s", my_mqtt_topics)

    if loop:
        if not batch:
            cam.open()

        while loop:
            if batch:
                cam = edge_camera.FileCamera(
                    batch_files.pop(),
                    args.device_id,
                    logger,
                    args.stdout,
                    protobuf,
                )
                cam.open()

            if mqtt_sub:
                if not mqtt_msg:
                    continue
                elif mqtt_topic not in my_mqtt_topics:
                    mqtt_msg = None
                    if printout:
                        logger.debug("Ignoring unknown topic: %s", mqtt_topic)
                    continue
                elif mqtt_msg == "quit" or mqtt_msg == "exit":
                    if printout:
                        logger.info("Quit command received via MQTT..")
                    exit_gracefully(cam, mqtt_client)
                elif mqtt_msg.startswith("get_frame"):
                    if printout:
                        logger.info(
                            "MQTT command: %s: %s", mqtt_topic, mqtt_msg
                        )
                    if mqtt_msg.startswith("get_frame,file://"):
                        if args.protocol == "file":
                            new_file_path = mqtt_msg[len("get_frame,file://") :]
                            cam.set_address(new_file_path)
                            logger.info(
                                "Image file address set to: %s", new_file_path
                            )
                        else:
                            logger.error(
                                "Setting address in MQTT get_frame command is "
                                "only supported for file protocol"
                            )
                    mqtt_msg = None
                else:
                    if printout:
                        logger.info(
                            "Unknown MQTT command received: %s", mqtt_msg
                        )
                    mqtt_msg = None
                    continue
            now = datetime.datetime.now()
            timestamp_rfc3339 = rfc3339(now)
            timestamp_sec = now.timestamp()
            ts = int(timestamp_sec * 1000)

            if "genicam" in args.protocol and args.raw_write:
                sensor_array, height, width, buffer = cam.get_raw()
                if not height:
                    if printout:
                        logger.info("Genicam raw imager acquiry failed")
                    continue

                if args.temp_format == "C":
                    sensor_array_thermal = sensor_array * 0.4 - 273.15
                elif args.temp_format == "F":
                    sensor_array_thermal = (
                        sensor_array * 0.4 - 273.15
                    ) * 9 / 5 + 32
                else:
                    # default to Kelvin
                    sensor_array_thermal = sensor_array * 0.4
                payload_struct_thermal["temp_avg"] = np.average(
                    sensor_array_thermal
                )
                payload_struct_thermal["temp_min"] = sensor_array_thermal.min()
                payload_struct_thermal["temp_max"] = sensor_array_thermal.max()
                payload_struct_thermal["temp_array"] = sensor_array.tolist()
                payload_struct_thermal["ts"] = timestamp_rfc3339
                payload_byte_array = create_pubsub_payload(
                    payload_struct_thermal, logger
                )
                filename = "{}{}-{}.bin".format(
                    args.raw_write_path, args.device_id, ts
                )
                with open(filename, "wb") as f:
                    f.write(payload_byte_array)
                    f.close()

            if args.img_write or args.ml or protobuf:
                if args.stream_delay and not continuous:
                    if printout:
                        logger.info(
                            "Stream_delay %sms before capturing frame",
                            args.stream_delay,
                        )
                    time.sleep(args.stream_delay / 1000.0)
                if protobuf:
                    pil_img = None
                    if args.protocol == "genicam":
                        edge_camera.print_without_eol(
                            cam.get_frame(args, sensor_array, height, width)
                        )
                    else:
                        edge_camera.print_without_eol(cam.get_frame())
                elif args.protocol == "genicam":
                    pil_img = cam.get_frame(args, sensor_array, height, width)
                else:
                    pil_img = cam.get_frame()

                if pil_img:
                    if crop:
                        pil_img = pil_img.crop(
                            (
                                args.crop_left,
                                args.crop_top,
                                args.crop_right,
                                args.crop_bottom,
                            )
                        )

                    if args.width > 0 and args.height > 0:
                        w, h = pil_img.size
                        if w != args.width or h != args.height:
                            pil_img = pil_img.resize((args.width, args.height))

                    if args.img_write:
                        filename = "{}{}-{}.png".format(
                            args.img_write_path, args.device_id, ts
                        )
                        if printout and not continuous:
                            logger.info("Writing image: %s", filename)
                        pil_img.save(filename)
                        if continuous and args.count > 0 and printout:
                            logger.info(
                                "Images written: %s/%s", count + 1, args.count
                            )

                    if args.ml:
                        byte_io = io.BytesIO()
                        pil_img.save(byte_io, "PNG")
                        byte_io.seek(0)
                        results = predict(
                            printout,
                            logger,
                            byte_io.read(),
                            ml_url,
                            request_body_template,
                        )
                        byte_io.seek(0)

                        if args.ml_write:
                            filename = "{}{}-{}.json".format(
                                args.ml_write_path, args.device_id, ts
                            )
                            logger.debug(
                                "Writing ML results JSON: %s", filename
                            )
                            with open(filename, "w", encoding="utf-8") as f:
                                f.write(json.dumps(results))
                            f.close()
                        else:
                            if printout:
                                logger.info(results)

                    if "results" in args.pubsub and args.ml:
                        payload_struct["ts"] = timestamp_rfc3339
                        payload_struct["file_id"] = ts
                        payload_struct["results"] = results
                        payload_byte_array = create_pubsub_payload(
                            payload_struct, logger
                        )
                        transmit_pubsub(
                            printout,
                            logger,
                            publisher,
                            args,
                            payload_byte_array,
                        )

                    if args.mqtt and args.ml:
                        transmit_mqtt(
                            printout,
                            logger,
                            mqtt_client,
                            results,
                            args.mqtt_topic_results,
                        )

            time.sleep(args.sleep)
            if buffer:
                cam.queue(buffer)
            if single:
                loop = False
            elif (continuous or batch) and total_count > 0:
                count += 1
                if count >= total_count:
                    loop = False
            elif interactive:
                key = input(
                    "Press Enter to process another image.. Q to quit: "
                )
                if "q" in key or "Q" in key:
                    loop = False
    exit_gracefully(cam, mqtt_client)


if __name__ == "__main__":
    main()
