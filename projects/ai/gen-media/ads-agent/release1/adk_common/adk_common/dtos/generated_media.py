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


# pylint: disable=C0114, C0301, W0718
import base64

from pydantic import BaseModel


class GeneratedMedia(BaseModel):
    """
    This schema is used to represent a GenAI Image.
    """

    filename: str
    mime_type: str
    gcs_uri: str | None = None
    description: str | None = None
    title: str | None = None
    media_bytes: bytes | None = None


    def to_obj_sans_bytes(self) -> dict[str, str | None]:
        """
        Serializes the object to a JSON string without the img_bytes.
        """

        return {
            "filename": self.filename,
            "mime_type": self.mime_type,
            "description": self.description,
            "title": self.title,
            "gcs_uri": self.gcs_uri
        }


    def to_obj_with_base64_bytes(self) -> dict[str, str | None]:
        """
        Serializes the object to a JSON string without the img_bytes.
        """

        return {
            "filename": self.filename,
            "mime_type": self.mime_type,
            "description": self.description,
            "title": self.title,
            "gcs_uri": self.gcs_uri,
            "media_bytes": base64.b64encode(self.media_bytes).decode("utf-8") if self.media_bytes else None

        }


    @classmethod
    def from_dict(cls, data: dict) -> "GeneratedMedia":
        """
        Creates a GeneratedMedia object from a dictionary.
        Handles base64 encoded media_bytes if present.
        """
        media_bytes = data.get("media_bytes")
        if isinstance(media_bytes, str):
            try:
                media_bytes = base64.b64decode(media_bytes)
            except Exception:
                # If decoding fails, turn to None
                media_bytes = None
                pass
        else:
            media_bytes = None

        return cls(
            filename=data["filename"],
            mime_type=data["mime_type"],
            gcs_uri=data.get("gcs_uri"),
            description=data.get("description"),
            title=data.get("title"),
            media_bytes=media_bytes
        )
