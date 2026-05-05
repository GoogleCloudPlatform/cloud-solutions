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

# pylint: disable=C0114, C0301

import csv
import json
import os


def convert_geotargets_to_dict(csv_file_path):
    """
    Converts the geotargets CSV file into a dictionary where the key is the city name (lowercase)
    and the value is the complete row in the file.
    """
    geotargets_dict = {}

    if not os.path.exists(csv_file_path):
        print(f"Error: File not found at {csv_file_path}")
        return geotargets_dict

    with open(csv_file_path, mode="r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            city_name = row.get("Name")
            if city_name:
                # Making the key lowercase as requested
                geotargets_dict[city_name.lower()] = row

    return geotargets_dict


def convert_languages_to_dict(csv_file_path):
    """
    Converts the language codes CSV file into a dictionary where the key is the language name (lowercase)
    and the value is the complete row in the file.
    """
    languages_dict = {}

    if not os.path.exists(csv_file_path):
        print(f"Error: File not found at {csv_file_path}")
        return languages_dict

    with open(csv_file_path, mode="r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            language_name = row.get("Language name")
            if language_name:
                # Making the key lowercase
                languages_dict[language_name.lower()] = row

    return languages_dict


def save_dict_to_json(data, json_file_path):
    """
    Saves the dictionary to a JSON file.
    """
    with open(json_file_path, "w", encoding="utf-8") as jsonfile:
        json.dump(data, jsonfile, indent=4, ensure_ascii=False)
    print(f"JSON file created successfully at: {json_file_path}")


if __name__ == "__main__":
    # Path to the files relative to this script
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Geotargets
    '''csv_path_geo = os.path.join(current_dir, "geotargets-2026-02-25.csv")
    json_path_geo = os.path.join(current_dir, "geotargets.json")

    print("Converting geotargets...")
    targets_geo = convert_geotargets_to_dict(csv_path_geo)
    print(f"Total geotargets loaded: {len(targets_geo)}")

    if targets_geo:
        save_dict_to_json(targets_geo, json_path_geo)
        sample_key = next(iter(targets_geo))
        print(f"Sample Entry for '{sample_key}': {targets_geo[sample_key]}")'''

    # Languages
    csv_path_lang = os.path.join(current_dir, "languagecodes.csv")
    json_path_lang = os.path.join(current_dir, "languagecodes.json")

    print("\nConverting languages...")
    targets_lang = convert_languages_to_dict(csv_path_lang)
    print(f"Total languages loaded: {len(targets_lang)}")

    if targets_lang:
        save_dict_to_json(targets_lang, json_path_lang)
        sample_key = next(iter(targets_lang))
        print(f"Sample Entry for '{sample_key}': {targets_lang[sample_key]}")
