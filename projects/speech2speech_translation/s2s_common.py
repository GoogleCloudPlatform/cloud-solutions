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

"""Common functions for speech2speech clients."""
import datetime
import re
from google.api_core.client_options import ClientOptions
import google.api_core.exceptions
from google.cloud import storage
from google.cloud import texttospeech
from google.cloud import translate_v2 as translate
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech


def parse_gcs_url(url):
    """Parses a GCS URL and extracts the bucket name and path.

    Args:
      url: The GCS URL to parse.

    Returns:
      A dictionary containing the following keys:
        - bucket: The name of the bucket.
        - path: The path to the object within the bucket.

    Raises:
      ValueError: If the URL is not in the expected format.
    """
    match = re.match(r"^gs://(?P<bucket>[^/]+)/(?P<path>.*)$", url)
    if match:
        return match.groupdict()
    else:
        raise ValueError("Invalid GCS URL: {}".format(url))


def upload_file_to_gcs(project_id, gcs, filepath, filename, logger):
    """Uploads a local file to Google Cloud Storage.

    This function takes a local file path and filename, GCS bucket and path,
    and uploads the file to the specified GCS location.

    Args:
      project_id: Google Cloud project ID.
      gcs: A dictionary containing the GCS bucket name and path.
      filepath: The path to the local file to upload.
      filename: The name of the file to upload.
      logger: Logging object.

    Returns:
      The Google Cloud Storage URI of the uploaded file.
    """
    storage_client = storage.Client(project=project_id)

    bucket = storage_client.get_bucket(gcs["bucket"])

    gcs_uri_input_audio = "gs://" + gcs["bucket"] + "/" + gcs["path"] + filename
    blob = bucket.blob(gcs["path"] + filename)

    logger.info("Uploading %s to %s", filepath + filename, gcs_uri_input_audio)
    blob.upload_from_filename(filepath + filename)

    return gcs_uri_input_audio


def upload_variable_to_gcs(project_id, gcs, object_name, data, content_type):
    """Uploads data to Google Cloud Storage from memory.

    Args:
      project_id: Google Cloud project ID.
      gcs: A dictionary containing the GCS bucket name and path.
      object_name: The name of the object to upload.
      data: The data to upload (bytes or string).
      content_type: The content type of the data.

    Returns:
      The Google Cloud Storage URI of the uploaded file.
    """
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.get_bucket(gcs["bucket"])
    blob = bucket.blob(gcs["path"] + object_name)

    if isinstance(data, str):
        data = data.encode("utf-8")

    blob.upload_from_string(data, content_type=content_type)
    gcs_uri = "gs://" + gcs["bucket"] + "/" + gcs["path"] + object_name

    return gcs_uri


def speech_to_text(
    project_id,
    location,
    source_language_code,
    stt_model,
    stt_timeout,
    gcs_uri_input_audio,
    logger,
):
    """Transcribes speech audio to text.

    Args:
      project_id: Google Cloud project ID.
      location: Google Cloud location to use.
      source_language_code: Source language code for STT.
      stt_model: Speech to Text model to use.
      stt_timeout: Timeout for STT operation in seconds.
      gcs_uri_input_audio: Google Cloud Storage URI of the input audio file.
      logger: Logger object.

    Returns:
      Speech-to-Text response object.
    """
    client = SpeechClient(
        client_options=ClientOptions(
            api_endpoint=f"{location}-speech.googleapis.com",
        )
    )

    recognition_features = cloud_speech.RecognitionFeatures(
        enable_automatic_punctuation=True,
        enable_spoken_punctuation=True,
        enable_word_time_offsets=True,
        profanity_filter=False,
        max_alternatives=1,
    )

    recognition_config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=[source_language_code],
        model=stt_model,
        features=recognition_features,
    )

    metadata = cloud_speech.BatchRecognizeFileMetadata(uri=gcs_uri_input_audio)

    request = cloud_speech.BatchRecognizeRequest(
        recognizer=(
            f"projects/{project_id}/locations/" f"{location}/recognizers/_"
        ),
        config=recognition_config,
        files=[metadata],
        recognition_output_config=cloud_speech.RecognitionOutputConfig(
            inline_response_config=cloud_speech.InlineOutputConfig(),
        ),
    )

    operation = client.batch_recognize(request=request)

    logger.info(
        "Waiting for STT operation to complete... timeout: %ss", stt_timeout
    )
    response = operation.result(timeout=stt_timeout)

    return response


def parse_stt_response(stt_response, uri, alt, logger):
    """Parses Speech-to-Text response and chooses alternative per sentence.

    Args:
      stt_response: Speech-to-Text response object.
      uri: Google Cloud Storage URI of the input audio file.
      alt: Alternative to choose from the response.
      logger: Logger object.

    Returns:
      Transcript string.
    """
    transcript = []

    for result in stt_response.results[uri].transcript.results:
        transcript.append(result.alternatives[alt].transcript)
    logger.debug("STT Transcript for alternative %s: %s", alt, transcript)
    if isinstance(transcript, bytes):
        transcript = transcript.decode("utf-8")

    return "".join(transcript)


def translate_text(target_language, transcript, logger):
    """Translates text to target language.

    Args:
      target_language: Target language.
      transcript: Transcript string.
      logger: Logger object.

    Returns:
      Translate response object.
    """
    translate_client = translate.Client()

    logger.info("Translating text to: %s", target_language)
    translate_result = translate_client.translate(
        transcript, target_language=target_language
    )

    return translate_result


def text_to_speech(
    project_id,
    location,
    target_voice,
    target_voice_gender,
    target_language_code,
    text,
    tts_timeout,
    gcs,
    output_audio_file_name,
    logger,
    prefix,
):
    """Converts text to speech.

    Args:
      project_id: Google Cloud project ID.
      location: Google Cloud location to use.
      target_voice: TTS voice to use.
      target_voice_gender: Gender to use with TTS voice.
      target_language_code: Target language code.
      text: Text to convert to speech.
      tts_timeout: Timeout for TTS operation in seconds.
      gcs: A dictionary containing the GCS bucket name and path.
      output_audio_file_name: Output audio file name.
      logger: Logger object.
      prefix: Optional file name prefix.
    """
    client = texttospeech.TextToSpeechLongAudioSynthesizeClient()

    input_text = texttospeech.SynthesisInput(text=text)

    gender = (
        texttospeech.SsmlVoiceGender.FEMALE
        if target_voice_gender == "female"
        else texttospeech.SsmlVoiceGender.MALE
    )

    voice = texttospeech.VoiceSelectionParams(
        language_code=target_language_code,
        name=target_voice,
        ssml_gender=gender,
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        speaking_rate=1.0,
    )

    parent = f"projects/{project_id}/locations/{location}"

    gcs_path = "gs://" + gcs["bucket"] + "/" + gcs["path"]

    request = texttospeech.SynthesizeLongAudioRequest(
        parent=parent,
        input=input_text,
        audio_config=audio_config,
        voice=voice,
        output_gcs_uri=(f"{gcs_path}{prefix}{output_audio_file_name}"),
    )

    logger.info(
        "Waiting for TTS operation to complete... timeout: %ss", tts_timeout
    )
    try:
        operation = client.synthesize_long_audio(request=request)
        result = operation.result(timeout=tts_timeout)
        logger.info(
            "TTS output written to: %s",
            f"{gcs_path}{prefix}{output_audio_file_name}",
        )
        if result:
            logger.info("TTS operation result: %s", result)
    except google.api_core.exceptions.GoogleAPICallError as e:
        logger.error("TTS operation failed: %s. Exiting", e)
        exit(1)


def list_tts_voices(logger):
    """Lists available voices for text-to-speech.

    Args:
      logger: Logging object.
    """
    client = texttospeech.TextToSpeechClient()
    voices = client.list_voices()

    output = []

    for voice in voices.voices:
        output.append(f"\nName: {voice.name}\n")

        for language_code in voice.language_codes:
            output.append(f"Supported language: {language_code}\n")

        ssml_gender = texttospeech.SsmlVoiceGender(voice.ssml_gender)
        output.append(f"SSML Voice Gender: {ssml_gender.name}\n")
        output.append(
            f"Natural Sample Rate Hz: {voice.natural_sample_rate_hertz}\n"
        )

    logger.info("".join(output))


def list_translate_languages(logger):
    """Lists available languages for translation.

    Args:
      logger: Logging object.
    """
    translate_client = translate.Client()
    results = translate_client.get_languages()

    output = []
    output.append("\n")

    for language in results:
        output.append("Name: " + language["name"] + "\n")
        output.append("Language: " + language["language"] + "\n")

    logger.info("".join(output))


def generate_filename_prefix(filename_prefix):
    """Generates filename prefix based on config.

    Args:
      filename_prefix: String of preferred prefix type.

    Returns:
      Filename prefix.
    """
    if "timestamp" not in filename_prefix:
        return None

    now = datetime.datetime.now()
    prefix = now.isoformat() + "_"
    return prefix
