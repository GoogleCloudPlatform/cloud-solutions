# Copyright 2023 Google LLC
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

"""Generate voice from image."""

import argparse
import configparser
import io
import os
import subprocess

import cv2
from google.cloud import texttospeech
from PIL import Image as PIL_Image
from pydub import AudioSegment
from pydub.playback import play
from vertexai.preview.vision_models import Image
from vertexai.preview.vision_models import ImageCaptioningModel


CONFIG_FILE = "config.ini"


def parse_config_args(config_file):
  """Parses config.ini and command line args.

  Parses first the .ini -style config file, and then command line args.
  CLI args overwrite default values from the config file.

  Args:
    config_file: path to the config.ini

  Returns:
    Configparser config

  Raises:
    None
  """
  # Create a config parser object
  config = configparser.ConfigParser()
  config["DEFAULT"] = {"input": 0,
                       "credentials": "credentials.json"}
  config["parameters"] = {}

  # Create an argument parser
  parser = argparse.ArgumentParser()

  # Read the configuration file
  read_config = config.read(config_file)
  if not read_config:
    print("{} not found. Using command line args only".format(config_file))
    # Add arguments for each configuration value using hardcoded defaults
    parser.add_argument("--input",
                        default=config["DEFAULT"]["input"],
                        type=str,
                        help="Camera device number")
    parser.add_argument("--credentials",
                        default=config["DEFAULT"]["credentials"],
                        type=str,
                        help=("Google Cloud Service account JSON key. "
                              "Default: ./credentials.json"))
    parser.add_argument("--project_id",
                        required=True,
                        type=str,
                        help="Google Cloud Project ID string")
  else:
    # Add arguments for each configuration value using read file
    # for fallback defaults
    parser.add_argument("--input",
                        default=config["parameters"]["input"],
                        type=str,
                        help="Camera device number")
    parser.add_argument("--credentials",
                        default=config["parameters"]["credentials"],
                        type=str,
                        help=("Google Cloud Service account JSON key. "
                              "Default: ./credentials.json"))
    parser.add_argument("--project_id",
                        default=config["parameters"]["project_id"],
                        type=str,
                        help="Google Cloud Project ID string")

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


def query_imagen_caption(input_img):
  """Calls the VertexAI Imagen LVM for image captioning.

  Args:
    input_img: the input image

  Returns:
    String with image captions

  Raises:
    None
  """
  print("Querying Imagen captioning...", end="", flush=True)
  model = ImageCaptioningModel.from_pretrained("imagetext@001")
  image = Image(input_img)
  captions = model.get_captions(
      image=image,
      # Optional:
      number_of_results=1,
      language="en",
  )
  if not captions:
    print("Not OK")
    return None
  else:
    print("OK")
    return captions[0]


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


def tts_captions(captions, tts_client):
  """Uses Text-to-Speech AI to convert captions to speech.

  Args:
    captions: the caption used for speech synthesis
    tts_client: the tts service client

  Returns:
    response.audio_content

  Raises:
    None
  """
  print("Querying Cloud Text-to-Speech...", end="", flush=True)
  # Set the text input to be synthesized
  synthesis_input = texttospeech.SynthesisInput(text=captions)

  # Build the voice request, select the language code ("en-US") and the ssml
  # voice gender ("neutral")
  voice = texttospeech.VoiceSelectionParams(
      language_code="en-US", name="en-US-Neural2-G"
  )

  # Select the type of audio file you want returned
  audio_config = texttospeech.AudioConfig(
      audio_encoding=texttospeech.AudioEncoding.MP3
  )

  # Perform the text-to-speech request on the text input with the selected
  # voice parameters and audio file type
  response = tts_client.synthesize_speech(
      input=synthesis_input, voice=voice, audio_config=audio_config
  )

  if not response:
    print("Not OK")
    return(None)
  else:
    print("OK")
    return(response.audio_content)


def convert_image(opencv_image, byte_io):
  """Converts an OpenCV frame to bytes.

  Args:
    opencv_image: the image object
    byte_io: a byte io object to save the result

  Returns:
    byte_io

  Raises:
    None
  """
  byte_io.seek(0)
  color_converted = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB)
  pil_img = PIL_Image.fromarray(color_converted)
  pil_img.save(byte_io, "PNG")
  byte_io.seek(0)
  return byte_io


def main():
  config = parse_config_args(CONFIG_FILE)

  input_dev = int(config["parameters"]["input"])

  # Set the environment variable GOOGLE_APPLICATION_CREDENTIALS to
  # the path of your Google Cloud service account key file.
  os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
      config["parameters"]["credentials"]
  )

  # Instantiates a TTS client
  tts_client = texttospeech.TextToSpeechClient()

  # Open the camera feed
  print("Opening camera: {}".format(input_dev))
  # cap = cv2.VideoCapture(input_dev)
  cap = cv2.VideoCapture(input_dev)
  cap.set(3, 640)
  cap.set(4, 480)

  if not cap.isOpened():
    print("Cannot open camera {}".format(input_dev))
    exit(1)

  print("Select the camera view window by clicking it")
  print("Press <space> to caption the camera view. Press q to quit")

  byte_io = io.BytesIO()

  while cap.isOpened():
    ret, frame = cap.read()
    # if frame is read correctly ret is True
    if not ret:
      continue
    cv2.imshow("Imagen Voice Captioning", frame)
    pressed = cv2.waitKey(1)
    if pressed == ord(" "):
      # Query imagen
      byte_io = convert_image(frame, byte_io)
      captions = query_imagen_caption(byte_io.read())

      if captions:
        audio = None
        # Query TTS
        audio = tts_captions(captions, tts_client)

        if audio:
          audiosegment = AudioSegment.from_file(io.BytesIO(audio), format="mp3")
          play(audiosegment)
    elif pressed == ord("q"):
      break

  cap.release()
  cv2.destroyAllWindows()
  exit(0)


if __name__ == "__main__":
  main()
