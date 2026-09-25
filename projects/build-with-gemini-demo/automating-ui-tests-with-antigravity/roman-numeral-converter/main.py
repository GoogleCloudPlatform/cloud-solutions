# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Flask web application for converting numbers to Roman numerals."""

import logging
import os

import converter
from flask import Flask, render_template, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route("/", methods=["GET"])
def home_page():
    """Renders the home page."""
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():
    """Converts the input number to a Roman numeral."""
    number = request.form.get("number", "").strip()
    try:
        roman = converter.number_to_roman(number)
    except (ValueError, TypeError):
        logger.warning("Invalid number input received: %s", number)
        return (
            render_template(
                "convert.html",
                number=number,
                error="Please enter a valid positive integer.",
            ),
            400,
        )
    return render_template("convert.html", number=number, roman=roman)


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(
        debug=debug_mode, host="0.0.0.0", port=int(os.environ.get("PORT", 8080))
    )
