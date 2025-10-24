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

"""
Utilities for creating Dialogflow fulfillment
response messages.
"""

import logging
import os


def shopping_cart(request_json):
    """
    Construct Dialogflow Rich response message for
    Shopping cart.

    Args:
      request_json: shopping cart object.
    Returns:
      Dialogflow Rich response message.
    """
    payloads = []
    total = 0
    text = ""
    logging.debug("request_json=%s", request_json)
    for item in request_json["items"]:
        subtotal = round(item["quantity"] * item["price"], 2)
        total = total + subtotal
        text = text + f"""* {item["title"]} * {item["quantity"]}{os.linesep}"""
        payload = {
            "type": "info",
            "title": f"""{item["title"]} X {item["quantity"]}""",
            "subtitle": f"$ {subtotal}"
        }
        payloads.append(payload)

    payloads.append(
    {
        "type": "chips",
        "options": [
          {
            "text": f"Total: $ {total}",
            "anchor": {
              "href": "https://pay.google.com"
            }
          }
        ]
      }
    )
    shopping_cart_payload = {
        "payload":{
            "richContent": [
                payloads
            ]
        }
    }
    return shopping_cart_payload
