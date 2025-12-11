# Copyright 2025 Google LLC
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
GenMedia Marketing Solution Module.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# profile data for the demo
_BETTY_PROFILE_DATA = {
    "merchant_account": {
        "merchant_id": "MERCH001",
        "account_status": "ACTIVE",
        "account_open_date": "2020-08-15",
        "business_profile": {
            "legal_name": "Betty's Bakery LLC",
            "doing_business_as": "Betty's Bakery",
            "mcc_code": "5462",
            "website": "https://www.bettysbakery.com",
            "address": {
                "street": "200 10th Ave",
                "city": "New York",
                "state": "NY",
                "zip": "10011",
            },
        },
        "owner_profile": {
            "owner_id": "owner_F7G3H",
            "first_name": "Betty",
            "last_name": "Jones",
            "email": "betty@bettysbakery.com",
            "phone_number": "+1-212-555-1212",
        },
        "service_plan": {
            "plan_name": "GP Pro",
            "processing_rate_percent": 2.6,
            "per_transaction_fee_cents": 10,
            "enabled_payment_methods": [
                "Visa",
                "Mastercard",
                "Amex",
                "Discover",
                "Google Pay",
                "Apple Pay",
            ],
            "subscribed_services": [
                "Hosted Payment Fields",
                "Analytics Suite",
                "Dispute Manager",
                "Capital Advance Program",
            ],
        },
        "banking_details": {
            "payout_schedule": "DAILY",
            "bank_name": "Bank of America",
            "account_last4": "7890",
        },
        "account_health": {
            "ytd_processing_volume_usd": 157250.5,
            "chargeback_rate_percent": 0.02,
            "last_payout": {"date": "2025-10-29", "amount_usd": 450.75},
        },
    }
}


def load_merchant_profile() -> Dict[str, Any]:
    """
    Loads the hardcoded merchant profile for the demo.

    Returns:
        A dictionary containing the merchant profile.
    """
    logger.info("Loading hardcoded merchant profile for demo.")
    # Return the hardcoded dictionary directly
    return _BETTY_PROFILE_DATA
