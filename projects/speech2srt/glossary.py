# -*- coding: utf-8 -*-
#
# Copyright 2019 Google LLC
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

# ruff: noqa

"""Manage glossaries using the Google Cloud Translation API.

This module provides functionality for creating, updating, deleting, and
listing glossaries using the Google Cloud Translation API. Glossaries allow
you to customize translations by providing a set of term mappings between
source and target languages.

For more information about the Google Cloud Translation API, see:
https://cloud.google.com/translate/docs/reference/rest
"""

from google.cloud import translate_v3 as translate
from google.cloud.translate_v3 import UpdateGlossaryRequest
from google.protobuf.field_mask_pb2 import FieldMask
import argparse

def create_glossary(
    project_id: str,
    input_uri: str,
    glossary_id: str,
    source_lang_code: str,
    target_lang_code: str,
    location: str,
    timeout: int = 180,
) -> translate.Glossary:
    """
    Create a new equivalent term sets glossary.
    """

    client = translate.TranslationServiceClient()
    name = client.glossary_path(project_id, location, glossary_id)
    language_codes_set = translate.types.Glossary.LanguageCodesSet(
        language_codes=[source_lang_code, target_lang_code]
    )

    gcs_source = translate.types.GcsSource(input_uri=input_uri)

    input_config = translate.types.GlossaryInputConfig(gcs_source=gcs_source)

    glossary = translate.types.Glossary(
        name=name, language_codes_set=language_codes_set,
        input_config=input_config
    )

    parent = f"projects/{project_id}/locations/{location}"

    operation = client.create_glossary(parent=parent, glossary=glossary)

    result = operation.result(timeout)
    print(f"Created: {result.name}")
    print(f"Input Uri: {result.input_config.gcs_source.input_uri}")

    return result

def update_glossary(
    project_id: str,
    input_uri: str,
    glossary_id: str,
    location: str,
    timeout: int = 180,
) -> translate.Glossary:
    """
    Update an existing equivalent term sets glossary.
    """

    client = translate.TranslationServiceClient()

    name = client.glossary_path(project_id, location, glossary_id)

    gcs_source = translate.types.GcsSource(input_uri=input_uri)
    input_config = translate.types.GlossaryInputConfig(gcs_source=gcs_source)

    glossary = translate.types.Glossary(name=name, input_config=input_config)

    update_mask = FieldMask(paths=["input_config"])

    # Construct the update request
    request = UpdateGlossaryRequest(
        glossary=glossary,
        update_mask=update_mask
    )

    operation = client.update_glossary(request=request)

    result = operation.result(timeout)
    print(f"Updated: {result.name}")
    print(f"Input Uri: {result.input_config.gcs_source.input_uri}")

    return result


def delete_glossary(
    project_id: str,
    glossary_id: str,
    location: str,
    timeout: int = 180,
) -> translate.Glossary:
    """Delete a specific glossary based on the glossary ID.

    Args:
        project_id: The ID of the GCP project that owns the glossary.
        glossary_id: The ID of the glossary to delete.
        timeout: The timeout for this request.

    Returns:
        The glossary that was deleted.
    """
    client = translate.TranslationServiceClient()

    name = client.glossary_path(project_id, location, glossary_id)

    operation = client.delete_glossary(name=name)
    result = operation.result(timeout)
    print(f"Deleted: {result.name}")

    return result

def list_glossaries(
    project_id: str,
    location: str,
) -> None:
    """List Glossaries.

    Args:
        project_id: The GCP project ID.
    """
    client = translate.TranslationServiceClient()

    parent = f"projects/{project_id}/locations/{location}"

    # Iterate over all results
    for glossary in client.list_glossaries(parent=parent):
        print(f"Name: {glossary.name}")
        print(f"Entry count: {glossary.entry_count}")
        print(f"Input uri: {glossary.input_config.gcs_source.input_uri}")

        # Note: You can create a glossary using one of two modes:
        # language_code_set or language_pair. When listing the information for
        # a glossary, you can only get information for the mode you used
        # when creating the glossary.
        for language_code in glossary.language_codes_set.language_codes:
            print(f"Language code: {language_code}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create or modify a glossary for Google Translate API"
    )
    parser.add_argument("--project_id",
                        required=True,
                        help="Your Google Cloud Project ID")
    parser.add_argument("--input_uri",
                        help="GCS URI of your glossary CSV file")
    parser.add_argument("--glossary_id",
                        help="ID for your glossary")
    parser.add_argument("--source_lang_code",
                        help="Source Language Code")
    parser.add_argument("--target_lang_code",
                        help="Target Language Code")
    parser.add_argument("--location",
                        default="us-central1",
                        help="The location of the glossary")
    parser.add_argument("--timeout",
                        type=int,
                        default=180,
                        help="Timeout for the operation (in seconds)"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", action="store_true",
                       help="Create a new glossary")
    group.add_argument("--modify", action="store_true",
                       help="Modify an existing glossary")
    group.add_argument("--delete", action="store_true",
                       help="Delete an existing glossary")
    group.add_argument("--list", action="store_true",
                       help="List existing glossaries")

    args = parser.parse_args()

    if args.create:
        create_glossary(args.project_id, args.input_uri, args.glossary_id,
                        args.source_lang_code, args.target_lang_code,
                        args.location, args.timeout)
    elif args.modify:
        update_glossary(args.project_id, args.input_uri, args.glossary_id,
                        args.location, args.timeout)
    elif args.delete:
        delete_glossary(args.project_id, args.glossary_id,
                        args.location, args.timeout)
    elif args.list:
        list_glossaries(args.project_id, args.location)
