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

"""Translates speech audio from one language to another.

Args:
    project_id: The Google Cloud project ID.
    bucket_name: The name of the GCS bucket to which the audio file is uploaded.
    stt_model: The Speech-to-Text transcription model to use.
    source_language_code: The language code of the source audio.
    target_language: The language to translate the transcript to.
    target_language_code: The language code of the target language.
    target_voice: The Text-to-Speech voice to use for the translation.
    target_voice_gender: The gender of the generated voice. Male or female.
    input_audio_file_name: Input audio file name.
    input_audio_file_path: Input audio file path.
    output_audio_file_name: Output audio file name.
    log: Log level.
"""
import argparse
import configparser
import logging
import s2s_common as s2s


CONFIG_FILE = "config.ini"


def parse_config_args(config_file):
  """Parses config.ini and command line args.

  Parses first the .ini -style config file, and then command line args.
  CLI args overwrite default values from the config file.

  Args:
    config_file: Path to config file.

  Returns:
    Configparser config.
  """
  config = configparser.ConfigParser()
  config["parameters"] = {}

  try:
    config.read_file(open(config_file, encoding="utf-8"))
  except FileNotFoundError as e:
    print(f"Config file {config_file} cannot be read: {e}")
    return None

  parser = argparse.ArgumentParser()

  parser.add_argument("--project_id",
                      default=config["parameters"]["project_id"],
                      type=str,
                      help="The Google Cloud project ID.")
  parser.add_argument("--location",
                      default=config["parameters"]["location"],
                      type=str,
                      help="The Google Cloud location.")
  parser.add_argument("--gcs_path",
                      default=config["parameters"]["gcs_path"],
                      type=str,
                      help=("Google Cloud Storage path. "
                            "Example: gs://bucket_name/dir1/dir2/"))
  parser.add_argument("--stt_model",
                      default=config["parameters"]["stt_model"],
                      type=str,
                      help=("Speech to Text model. "
                            "Choices: long|short|telephony"))
  parser.add_argument("--stt_timeout",
                      default=config["parameters"]["stt_timeout"],
                      type=int,
                      help="Speech to Text operation timeout in seconds.")
  parser.add_argument("--stt_alternative",
                      default=config["parameters"]["stt_alternative"],
                      type=int,
                      help="Speech to Text results alternative index.")
  parser.add_argument("--input_audio_file_name",
                      default=config["parameters"]["input_audio_file_name"],
                      type=str,
                      help="Input audio file name.")
  parser.add_argument("--input_audio_file_path",
                      default=config["parameters"]["input_audio_file_path"],
                      type=str,
                      help="Input audio file path.")
  parser.add_argument("--output_audio_file_name",
                      default=config["parameters"]["output_audio_file_name"],
                      type=str,
                      help="Output audio file name.")
  parser.add_argument("--source_language_code",
                      default=config["parameters"]["source_language_code"],
                      type=str,
                      help="Source language code. Example: fi-FI.")
  parser.add_argument("--target_language",
                      default=config["parameters"]["target_language"],
                      type=str,
                      help="Target language. Example: en")
  parser.add_argument("--target_language_code",
                      default=config["parameters"]["target_language_code"],
                      type=str,
                      help="Target language code. Example: en-US")
  parser.add_argument("--target_voice",
                      default=config["parameters"]["target_voice"],
                      type=str,
                      help="Target voice. Example: en-US-Wavenet-A")
  parser.add_argument("--target_voice_gender",
                      default=config["parameters"]["target_voice_gender"],
                      type=str,
                      choices=["male", "female"],
                      help="Target voice gender. Choices: female|male")
  parser.add_argument("--tts_timeout",
                      default=config["parameters"]["tts_timeout"],
                      type=int,
                      help="Text to Speech operation timeout in seconds.")
  parser.add_argument("--log",
                      default=config["parameters"]["log"],
                      type=str,
                      help="Logging level. Example --log debug")
  parser.add_argument("--list_translate_languages",
                      action="store_true",
                      help="List available translation languages.")
  parser.add_argument("--list_voices",
                      action="store_true",
                      help="List available TTS voices.")
  parser.add_argument("--filename_prefix",
                      default=config["parameters"]["filename_prefix"],
                      type=str,
                      choices=["none", "timestamp"],
                      help=("Prefix for output file names. "
                            "Choices: none|timestamp"))
  parser.add_argument("--output_interim_files",
                      action="store_true",
                      help=("Output interim such as transcript "
                            "and translation, and upload them to GCS."))

  args = parser.parse_args()

  return args


def main():
  """Translates speech audio from one language to another.

  Args: None
  """
  args = parse_config_args(CONFIG_FILE)
  if not args:
    print("Failed to parse config file. Exiting.")
    exit(1)

  logger = logging.getLogger()
  logger.setLevel(args.log.upper())
  ch = logging.StreamHandler()
  formatter = logging.Formatter(
      "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  )
  ch.setFormatter(formatter)
  logger.addHandler(ch)

  logger.info("Main started")
  logger.info("args: %s", args)

  if args.list_voices:
    s2s.list_tts_voices(logger)
    exit(0)
  elif args.list_translate_languages:
    s2s.list_translate_languages(logger)
    exit(0)

  gcs = s2s.parse_gcs_url(args.gcs_path)
  if not gcs["path"].endswith("/"):
    gcs["path"] += "/"
  logger.info("GCS URL: %s", args.gcs_path)
  logger.debug("GCS bucket: %s", gcs["bucket"])
  logger.debug("GCS path: %s", gcs["path"])

  prefix = s2s.generate_filename_prefix(args.filename_prefix) or ""
  logger.info("Filename prefix: %s", prefix)

  gcs_uri_input_audio = s2s.upload_file_to_gcs(
      args.project_id, gcs, args.input_audio_file_path,
      args.input_audio_file_name, logger)

  stt_response = s2s.speech_to_text(
      args.project_id, args.location, args.source_language_code,
      args.stt_model, args.stt_timeout, gcs_uri_input_audio, logger)

  transcript = s2s.parse_stt_response(
      stt_response, gcs_uri_input_audio, args.stt_alternative, logger)

  translate_result = s2s.translate_text(
      args.target_language, transcript, logger)
  logger.debug("Text (%s): %s", translate_result["detectedSourceLanguage"],
               translate_result["input"])
  logger.debug("\nTranslation (%s): %s", args.target_language,
               translate_result["translatedText"])

  s2s.text_to_speech(args.project_id, args.location, args.target_voice,
                     args.target_voice_gender, args.target_language_code,
                     translate_result["translatedText"], args.tts_timeout,
                     gcs, args.output_audio_file_name, logger, prefix)

  if args.output_interim_files:
    uri = s2s.upload_variable_to_gcs(
        args.project_id, gcs, prefix + "transcript.txt",
        transcript, "text/plain; charset=utf-8")
    logger.info("Transcript written to: %s", uri)

    uri = s2s.upload_variable_to_gcs(
        args.project_id, gcs, prefix + "translation.txt",
        translate_result["translatedText"], "text/plain; charset=utf-8")
    logger.info("Translation written to: %s", uri)

if __name__ == "__main__":
  main()
