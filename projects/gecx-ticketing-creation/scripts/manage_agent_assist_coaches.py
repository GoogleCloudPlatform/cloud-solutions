#!/usr/bin/env python3

# Copyright 2026 Google LLC
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

# -*- coding: utf-8 -*-

# pylint: disable=protected-access
"""Dialogflow Agent Assist AI Coach Generator Export & Deployment Tool.

Used in cross-project IaC flows:
1. export: Export configured AI Coach Generator from an existing GCP project to
   a local JSON file.
2. deploy: Rebuild/create the AI Coach Generator from a local JSON file on the
   target GCP project and output its new resource path.
"""

import argparse
import json
import os
import sys

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import dialogflow_v2beta1 as dialogflow
from google.protobuf import field_mask_pb2, json_format


def get_client():
    """Return GeneratorsClient for Agent Assist global endpoint."""
    return dialogflow.GeneratorsClient()


def export_generator(
    project_id: str, generator_name_or_id: str, output_filepath: str
):
    """Export an existing generator configuration to a local JSON file."""
    print("=============================================")
    print(f"  Exporting AI Coach Generator from project [{project_id}]...")
    client = get_client()

    # Resolve full resource path
    if "/" not in generator_name_or_id:
        parent = (
            f"projects/{project_id}/locations/global/generators/"
            f"{generator_name_or_id}"
        )
    else:
        parent = generator_name_or_id

    try:
        print(f"  Fetching resource: {parent}")
        generator = client.get_generator(name=parent)

        # Convert proto message to python dict
        generator_dict = json_format.MessageToDict(
            generator._pb, preserving_proto_field_name=True
        )

        # Clean up output JSON: remove project-specific fields like name,
        # create_time, update_time
        generator_dict.pop("name", None)
        generator_dict.pop("create_time", None)
        generator_dict.pop("update_time", None)

        # Save to file
        os.makedirs(os.path.dirname(output_filepath) or ".", exist_ok=True)
        with open(output_filepath, "w", encoding="utf-8") as file_handle:
            json.dump(generator_dict, file_handle, ensure_ascii=False, indent=2)

        print(
            f"✅ Export successful! Config file written to: {output_filepath}"
        )
        print("=============================================")

    except (GoogleAPICallError, OSError, ValueError) as e:
        print(f"❌ Export failed: {e}")
        sys.exit(1)


def deploy_generator(
    project_id: str, config_filepath: str, generator_id_to_create: str
) -> str:
    """Deploy or recreate an AI Coach Generator from a local JSON config."""
    print("=============================================")
    print(f"  Deploying AI Coach Generator in project [{project_id}]...")
    print(f"  Config file path: {config_filepath}")
    print(f"  Generator ID   : {generator_id_to_create}")
    print("=============================================")

    client = get_client()
    parent = f"projects/{project_id}/locations/global"

    # Load configuration
    if not os.path.exists(config_filepath):
        print(f"❌ Error: Config file not found {config_filepath}")
        sys.exit(1)

    with open(config_filepath, "r", encoding="utf-8") as file_handle:
        config_data = json.load(file_handle)

    # Filter custom properties used for UI/DB mapping
    config_data.pop("coach_id", None)
    config_data.pop("name", None)
    config_data.pop("conversation_profile_id", None)
    config_data.pop("enabled", None)
    config_data.pop("avatar_url", None)

    # Convert dict to Generator Proto message
    generator = dialogflow.Generator()
    json_format.ParseDict(config_data, generator._pb)

    # Determine full target resource name
    target_name = f"{parent}/generators/{generator_id_to_create}"

    # Check if target generator already exists
    try:
        existing = client.get_generator(name=target_name)
        print(
            "ℹ️ Detected existing generator with the same name:"
            f" {existing.name}"
        )

        # Delete and recreate for a clean deployment rebuild
        print("Updating generator...")
        client.delete_generator(name=target_name)
        print("Deleted old generator, recreating...")
    except GoogleAPICallError:
        # Does not exist, proceed to create
        pass

    # Create the generator
    try:
        response = client.create_generator(
            parent=parent,
            generator=generator,
            generator_id=generator_id_to_create,
        )
        print("✅ Generator successfully deployed!")
        print(f"Resource path: {response.name}")
        print("=============================================")

        # Print resource name to stdout
        print(response.name)
        return response.name

    except GoogleAPICallError as e:
        print(f"❌ Deployment failed: {e}")
        sys.exit(1)


def link_generator_to_profile(
    project_id: str, conversation_profile_id_or_path: str, generator_name: str
):
    """Link a deployed Generator resource name to a Conversation Profile."""
    print("=============================================")
    print("  Linking AI Coach Generator to conversation profile...")
    print(f"  Project ID           : {project_id}")
    print(f"  Conversation Profile : {conversation_profile_id_or_path}")
    print(f"  Generator Resource   : {generator_name}")
    print("=============================================")

    client = dialogflow.ConversationProfilesClient()
    parent = f"projects/{project_id}/locations/global"

    profile_path = None
    if "/" in conversation_profile_id_or_path:
        profile_path = conversation_profile_id_or_path
    else:
        try:
            print("  Searching/resolving conversation profile path...")
            profiles = client.list_conversation_profiles(parent=parent)
            for p in profiles:
                if (
                    p.display_name == conversation_profile_id_or_path
                    or p.name.endswith(f"/{conversation_profile_id_or_path}")
                ):
                    profile_path = p.name
                    print(
                        f"  Found matching conversation profile: {profile_path}"
                        f" (Display Name: {p.display_name})"
                    )
                    break
        except GoogleAPICallError as e:
            print(f"  Warning while listing conversation profiles: {e}")

        if not profile_path:
            profile_path = (
                f"{parent}/conversationProfiles/"
                f"{conversation_profile_id_or_path}"
            )

    try:
        # Build new profile object
        sug_cfg = (
            dialogflow.HumanAgentAssistantConfig.SuggestionConfig(
                generators=[generator_name]
            )
        )
        asst_cfg = dialogflow.HumanAgentAssistantConfig(
            human_agent_suggestion_config=sug_cfg
        )
        profile = dialogflow.ConversationProfile(
            name=profile_path,
            human_agent_assistant_config=asst_cfg,
        )

        update_mask = field_mask_pb2.FieldMask(
            paths=[
                "human_agent_assistant_config.human_agent_suggestion_config"
                ".generators"
            ]
        )

        print("  Sending API request to update profile...")
        response = client.update_conversation_profile(
            conversation_profile=profile, update_mask=update_mask
        )
        print(
            "✅ Linked successfully! Updated conversation profile:"
            f" {response.name}"
        )
        print("=============================================")

    except GoogleAPICallError as e:
        print(f"❌ Linking failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Manage Dialogflow Agent Assist AI Coach Generators (Export/Deploy)"
        )
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    # Export parser
    export_parser = subparsers.add_parser(
        "export", help="Export an existing AI Coach Generator to JSON"
    )
    export_parser.add_argument(
        "--project",
        default=os.getenv("GCP_PROJECT_ID"),
        help="Source GCP Project ID",
    )
    export_parser.add_argument(
        "--generator",
        required=True,
        help="Generator ID or full resource name to export",
    )
    export_parser.add_argument(
        "--output",
        required=True,
        help=(
            "Output file path (e.g."
            " terraform/assets/coaches/my_generator.json)"
        ),
    )

    # Deploy parser
    deploy_parser = subparsers.add_parser(
        "deploy", help="Deploy/Rebuild an AI Coach Generator from JSON"
    )
    deploy_parser.add_argument(
        "--project",
        default=os.getenv("GCP_PROJECT_ID"),
        help="Target GCP Project ID",
    )
    deploy_parser.add_argument(
        "--config", required=True, help="Path to the JSON configuration file"
    )
    deploy_parser.add_argument(
        "--id",
        required=True,
        help=(
            "ID to assign to the deployed generator"
            " (e.g. my-coaching-generator)"
        ),
    )

    # Link parser
    link_parser = subparsers.add_parser(
        "link",
        help=(
            "Link a deployed Generator resource name to a Conversation"
            " Profile"
        ),
    )
    link_parser.add_argument(
        "--project",
        default=os.getenv("GCP_PROJECT_ID"),
        help="Target GCP Project ID",
    )
    link_parser.add_argument(
        "--profile",
        required=True,
        help="Conversation Profile ID or full resource name",
    )
    link_parser.add_argument(
        "--generator",
        required=True,
        help="Generator resource name (e.g. projects/.../generators/...)",
    )

    args = parser.parse_args()

    if not args.project:
        # Load from .env if present
        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as env_file_handle:
                for line in env_file_handle:
                    if line.startswith("GCP_PROJECT_ID="):
                        args.project = (
                            line.strip().split("=")[1].replace('"', "")
                        )
                        break

    if not args.project:
        print(
            "❌ Error: Please provide --project parameter or set GCP_PROJECT_ID"
            " environment variable."
        )
        sys.exit(1)

    if args.action == "export":
        export_generator(args.project, args.generator, args.output)
    elif args.action == "deploy":
        deploy_generator(args.project, args.config, args.id)
    elif args.action == "link":
        link_generator_to_profile(args.project, args.profile, args.generator)
