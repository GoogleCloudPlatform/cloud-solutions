# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Generatively change image objects or background."""

import argparse
import base64
import configparser
import io
import json
import os
import subprocess

import cv2
from google.cloud import vision
import numpy as np
import requests


CONFIG_FILE = "config.ini"


def parse_config_args(config_file):
  """Parses config.ini and command line args.

  Parses first the .ini -style config file, and then command line args.
  CLI args overwrite default values from the config file.

  Args:
    config_file: Path to config file

  Returns:
    Configparser config

  Raises:
    None
  """
  # Create a config parser object
  config = configparser.ConfigParser()
  config["DEFAULT"] = {"mask": "mask.png",
                       "invert_mask": "False",
                       "output_json": "output.json",
                       "credentials": "credentials.json"
                       }
  config["parameters"] = {}

  # Create an argument parser
  parser = argparse.ArgumentParser()

  # Read the configuration file
  read_config = config.read(config_file)

  if not read_config:
    print("{} not found. Using command line args only".format(config_file))
    # Add arguments for each configuration value using hardcoded defaults
    parser.add_argument("--mask", default=config["DEFAULT"]["mask"], type=str,
                        help="Output mask file")
    parser.add_argument("--invert_mask",
                        default=config["DEFAULT"]["invert_mask"], type=str,
                        help="Invert mask; replace the background")
    parser.add_argument("--output_json",
                        default=config["DEFAULT"]["output_json"], type=str,
                        help="Output JSON file name for GenAI response")
    parser.add_argument("--credentials",
                        default=config["DEFAULT"]["credentials"], type=str,
                        help="Service account key. Default: credentials.json")
    parser.add_argument("--input", required=True, type=str,
                        help="Original image file")
    parser.add_argument("--label", required=True, type=str,
                        help="Object to detect e.g car | cat | tree")
    parser.add_argument("--prompt", required=True, type=str,
                        help="Imagen prompt for image generation")
    parser.add_argument("--project_id", required=True, type=str,
                        help="Google Cloud Project ID string")
  else:
    # Add arguments for each cfg value using read file for fallback defaults
    parser.add_argument("--input", default=config["parameters"]["input"],
                        type=str, help="Original image file")
    parser.add_argument("--label", default=config["parameters"]["label"],
                        type=str, help="Object to detect e.g car | cat")
    parser.add_argument("--prompt", default=config["parameters"]["prompt"],
                        type=str, help="Imagen prompt for image generation")
    parser.add_argument("--project_id",
                        default=config["parameters"]["project_id"], type=str,
                        help="Google Cloud Project ID string")
    parser.add_argument("--mask", default=config["parameters"]["mask"],
                        type=str, help="Output mask file")
    parser.add_argument("--invert_mask",
                        default=config["parameters"]["invert_mask"],
                        type=str, help="Invert mask; replace the background")
    parser.add_argument("--output_json",
                        default=config["parameters"]["output_json"], type=str,
                        help="Output JSON file name for GenAI response")
    parser.add_argument("--credentials",
                        default=config["parameters"]["credentials"], type=str,
                        help="Service account key. Default: credentials.json")

  # Parse the arguments
  args = parser.parse_args()

  # Update the configuration values with the command line arguments
  for arg in vars(args):
    config["parameters"][arg] = getattr(args, arg)

  print(dict(config["parameters"]))

  # Check for required values
  if not config["parameters"]["project_id"]:
    print("error: the following arguments are required: --project_id")
    exit(1)
  return config


def query_vision_api(input_img):
  """Queries Cloud Vision API for object classification.

  Uses Vision API to find objects in the input image.

  Args:
    input_img: user-supplied source image to infer

  Returns:
    objects found by Vision API

  Raises:
    None
  """
  # Create a Vision client object.
  client = vision.ImageAnnotatorClient()

  # Create an Image object from the image content.
  image = vision.Image(content=input_img)

  # Perform object detection on the image.
  objects = client.object_localization(
      image=image).localized_object_annotations
  return objects


def draw_mask_image(input_file, objects, mask_file, label, invert):
  """Draws mask image based on selected objects' coordinates.

  Draws a mask image for Imagen. Iterates through the objects 
  found by Vision API, and draws a mask for each object's coordinates, 
  if the object label matches the desired one.

  Args:
    input_file: user-supplied original image file name
    objects: list of objects found by Vision API
    mask_file: Imagen mask file name
    label: type of object set by the user
    invert: whether to invert the mask or not, for Imagen

  Returns:
    Boolean flag if the mask file was created or not

  Raises:
    None
  """
  # Create the mask image with same resolution as original
  orig_img = cv2.imread(input_file)
  mask_img = np.zeros((orig_img.shape), dtype=np.uint8)
  if invert:
    mask_img.fill(255)
  h, w, _ = orig_img.shape

  # draw the mask using Vision API bounding boxes
  masks = 0
  for object_ in objects:
    print("{} (confidence: {})".format(object_.name, object_.score))
    if object_.name.casefold() == label.casefold():
      masks += 1
      print("{} found! drawing mask".format(label))
      vertices = object_.bounding_poly.normalized_vertices
      x1 = int(vertices[0].x * w)
      y1 = int(vertices[0].y * h)
      x2 = int(vertices[2].x * w)
      y2 = int(vertices[2].y * h)
      if invert:
        cv2.rectangle(mask_img, (x1, y1), (x2, y2), (0, 0, 0), -1)
      else:
        cv2.rectangle(mask_img, (x1, y1), (x2, y2), (255, 255, 255), -1)

  mask_created = True
  if masks > 0:
    cv2.imwrite(mask_file, mask_img)
    print("Wrote mask to: {}".format(mask_file))
  else:
    print("No {} found in {}. Exiting".format(label, input_file))
    mask_created = False
  return mask_created


def query_imagen(prompt, input_img, mask_img, output_json, token, project_id):
  """Queries GenAI Imagen API for mask-based image editing.

  Uses Imagen to replace parts of the original image. The image mask 
  restricts the image generation work area.

  Args:
    prompt: the Imagen mask-based editing GenAI prompt
    input_img: the original source image
    mask_img: the editing mask image
    output_json: output file for writing Imagen response
    token: Gcloud access token within the GCP project
    project_id: GCP project ID

  Returns:
    Boolean, whether Imagen query was successful or not

  Raises:
    None
  """
  # Base64 encode the image and mask files
  img = base64.b64encode(input_img)
  mask_img = base64.b64encode(mask_img)

  # Create the JSON request body
  data = {
      "instances": [
          {
              "prompt": prompt,
              "image": {
                  "bytesBase64Encoded": img.decode("utf-8")
              },
              "mask": {
                  "image": {
                      "bytesBase64Encoded": mask_img.decode("utf-8")
                  }
              }
          }
      ],
      "parameters": {
          "sampleCount": 4,
          "sampleImageSize": "1024"
      }
  }

  # Make the API request
  headers = {
      "Authorization": "Bearer {}".format(token),
      "Content-Type": "application/json",
      "User-Agent": "Mozilla/5.0",
      "Accept-Encoding": "identity",
      "Accept": "*/*"}

  url = (
      "https://us-central1-aiplatform.googleapis.com/v1/projects/" +
      project_id +
      "/locations/us-central1/publishers/google/models/" +
      "imagegeneration@002:predict"
  )

  print("Querying Imagen...")
  response = requests.post(
      url,
      headers=headers,
      data=json.dumps(data, sort_keys=False, indent=2, separators=(",", ": ")),
      verify=True,
      timeout=None
  )

  imagen_success = True
  if not response:
    print("No or empty response from Imagen. Exiting")
    imagen_success = False
  else:
    with open(output_json, mode="w", encoding="utf-8") as f:
      f.write(response.text)
    print("Wrote Imagen response to: {}".format(output_json))
  return imagen_success


def get_gcloud_auth_token():
  """Gets the session authentication token using Gcloud tool.

  Uses the Gcloud tool to get the current project's authentication token.
  The token is used for authenticating the HTTP POST request to Imagen.
  The function uses subprocess to execute gcloud from the shell.

  Args:
    None

  Returns:
    String, containing the authentication token 

  Raises:
    None
  """
  cmd = ("gcloud", "auth", "print-access-token")
  p = subprocess.run(cmd, capture_output=True, text=True, check=False)
  return p.stdout.strip()


def write_images(output_json):
  """Parses Imagen response JSON and writes images to files.

  Parses the output.json response from Imagen, and for each 
  payload within, decodes them, and writes as image files on disk.

  Args:
    output_json: output file for writing Imagen response

  Returns:
    None

  Raises:
    None
  """
  with open(output_json, mode="r", encoding="utf-8") as f:
    data = json.load(f)
  i = 0
  for prediction in data["predictions"]:
    image_data = base64.b64decode(prediction["bytesBase64Encoded"])
    filename = "image" + str(i) + ".png"
    with open(filename, mode="wb", encoding="utf-8") as outfile:
      outfile.write(image_data)
    i += 1
  return i


def main():
  config = parse_config_args(CONFIG_FILE)

  label = config["parameters"]["label"]
  prompt = config["parameters"]["prompt"]
  input_file = config["parameters"]["input"]
  mask_file = config["parameters"]["mask"]
  output_json = config["parameters"]["output_json"]
  project_id = config["parameters"]["project_id"]

  if "True" in config["parameters"]["invert_mask"]:
    invert = True
  else:
    invert = False

  print("Target label:", label, "source image:",
        input_file, "project_id:", project_id)

  # Set env GOOGLE_APPLICATION_CREDENTIALS to the path service account key
  os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config["parameters"][
      "credentials"
  ]

  # Read the image file into memory.
  with io.open(input_file, mode="rb") as f:
    input_img = f.read()

  # find label location(s) bounding boxes with Cloud Vision API
  objects = query_vision_api(input_img)

  print("Number of objects found: {}".format(len(objects)))

  mask_created = draw_mask_image(input_file, objects, mask_file, label, invert)

  # Use GenAI Imagen to replace the object(s) or their background
  if mask_created:
    token = get_gcloud_auth_token()

    # Read the mask file into memory.
    with io.open(mask_file, mode="rb") as f:
      mask_img = f.read()

    imagen_success = query_imagen(
        prompt, input_img, mask_img, output_json, token, project_id
    )

    # Extract and write generated images
    if imagen_success:
      written = write_images(output_json)
      if written:
        print("Wrote {} output images".format(written))
  else:
    exit(1)


if __name__ == "__main__":
  main()
