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

# pylint: disable=C0114, C0115, C0301, E1136

import json
import os

from rapidfuzz import fuzz, process


class TargetingLookupTool:
    # Class-level cache attributes
    _locations_cache = None
    _languages_cache = None
    _location_names = None
    _language_names = None

    # Class-level file paths
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _locations_file = os.path.join(_current_dir, "geotargets.json") # Move this to Firestore
    _languages_file = os.path.join(_current_dir, "languagecodes.json")

    @classmethod
    def _load_locations(cls):
        """Loads locations from JSON file into class-level cache if not already loaded."""
        if cls._locations_cache is None:
            if os.path.exists(cls._locations_file):
                with open(cls._locations_file, "r", encoding="utf-8") as f:
                    cls._locations_cache = json.load(f)
                cls._location_names = list(cls._locations_cache.keys())
            else:
                cls._locations_cache = {}
                cls._location_names = []

    @classmethod
    def _load_languages(cls):
        """Loads languages from JSON file into class-level cache if not already loaded."""
        if cls._languages_cache is None:
            if os.path.exists(cls._languages_file):
                with open(cls._languages_file, "r", encoding="utf-8") as f:
                    cls._languages_cache = json.load(f)
                cls._language_names = list(cls._languages_cache.keys())
            else:
                cls._languages_cache = {}
                cls._language_names = []

    def search_location(self, user_input: str, threshold: int = 75):
        """
        Finds the best matching location ID for a given user string.
        """
        self._load_locations()
        if not self._location_names:
            return {"error": "Locations data not available"}

        match = process.extractOne(
            user_input, self._location_names, scorer=fuzz.token_sort_ratio
        )

        if match and match[1] >= threshold:
            matched_name, score, _ = match
            location_data = self._locations_cache[matched_name]
            return {
                "location_id": location_data.get("Criteria ID"),
                "matched_name": matched_name,
                "confidence": score,
            }

        return {
            "error": "Location match not confident enough",
            "top_suggestion": match[0] if match else None,
            "confidence": match[1] if match else 0,
        }

    def search_language(self, user_input: str, threshold: int = 75):
        """
        Finds the best matching language ID for a given user string.
        """
        self._load_languages()
        if not self._language_names:
            return {"error": "Languages data not available"}

        match = process.extractOne(
            user_input, self._language_names, scorer=fuzz.token_sort_ratio
        )

        if match and match[1] >= threshold:
            matched_name, score, _ = match
            language_data = self._languages_cache[matched_name]
            return {
                "language_id": language_data.get("Criterion ID"),
                "matched_name": matched_name,
                "confidence": score,
            }

        return {
            "error": "Language match not confident enough",
            "top_suggestion": match[0] if match else None,
            "confidence": match[1] if match else 0,
        }


    @staticmethod
    def search_in_dict(data_dict: dict, user_input: str, id_field: str, threshold: int = 75):
        """
        Finds the best matching ID for a given user string within a provided dictionary.
        """
        if not data_dict:
            return {"error": "Data dictionary is empty"}

        keys = list(data_dict.keys())
        match = process.extractOne(user_input, keys, scorer=fuzz.token_sort_ratio)

        if match and match[1] >= threshold:
            matched_name, score, _ = match
            item_data = data_dict[matched_name]
            return {
                "id": item_data.get(id_field),
                "matched_name": matched_name,
                "confidence": score,
            }

        return {
            "error": "Match not confident enough",
            "top_suggestion": match[0] if match else None,
            "confidence": match[1] if match else 0,
        }


# Usage within an ADK Agent tool definition
def get_location_id(query: str):
    lookup = TargetingLookupTool()
    return lookup.search_location(query)


def get_language_id(query: str):
    lookup = TargetingLookupTool()
    return lookup.search_language(query)
