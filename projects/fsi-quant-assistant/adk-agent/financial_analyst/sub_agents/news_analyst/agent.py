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

"""data_analyst_agent for finding information using google search"""
import os
from datetime import date, timedelta

import finnhub
from google.adk import Agent

from . import prompt

# https://finnhub.io/docs/api/
finnhub_api_key = os.getenv("FINNHUB_API_KEY")
print(f"The FinnHub API key is {finnhub_api_key}")
finnhub_client = finnhub.Client(api_key=finnhub_api_key)


def is_finnhub_api_key_defined():
    return finnhub_api_key is not None


def get_date_range(n_days):
    to_date = date.today()
    # Calculate the start date by subtracting n days
    from_date = to_date - timedelta(days=n_days)
    # Format dates into YYYY-MM-DD strings as required by the API
    to_date_str = to_date.strftime("%Y-%m-%d")
    from_date_str = from_date.strftime("%Y-%m-%d")
    return from_date_str, to_date_str


def get_quote(symbol: str) -> list[dict]:
    print(f"Fetches company quote for {symbol}.")
    result = finnhub_client.quote(symbol=symbol)
    print(f"Full API response for '{symbol}': {result}")
    return result


def get_company_news(symbol: str, n_days: int = 7) -> list[dict]:
    """Fetches company news for the last n days."""
    from_date_str, to_date_str = get_date_range(n_days)
    print(
        f"Fetching news for {symbol} from {from_date_str} to {to_date_str}..."
    )
    result = finnhub_client.company_news(
        symbol, _from=from_date_str, to=to_date_str
    )
    # print(f"Full API response for '{symbol}': {result}")
    return result


def get_company_profile(symbol: str) -> list[dict]:
    print(f"Fetches company profile for {symbol}.")
    result = finnhub_client.company_profile2(symbol=symbol)
    print(f"Full API response for '{symbol}': {result}")
    return result


def find_symbol(search_str: str) -> list[dict]:
    """Finds a stock symbol using the Finnhub API and logs the result."""
    print(f"Attempting to find symbol for query: '{search_str}'")
    result = finnhub_client.symbol_lookup(search_str)
    print(f"Full API response for '{search_str}': {result}")
    return result


def find_company_peers(symbol: str) -> list[dict]:
    """Finds company peers by symbol."""
    result = finnhub_client.company_peers(symbol=symbol)
    print(f"Full API response for '{symbol}': {result}")
    return result


def get_company_basic_financials(symbol: str) -> list[dict]:
    """Fetches company basic financials for a symbol."""
    result = finnhub_client.company_basic_financials(symbol, "all")
    print(f"Full API response for '{symbol}': {result}")
    return result


def get_insider_transactions(symbol: str, n_days: int = 30) -> list[dict]:
    from_date_str, to_date_str = get_date_range(n_days)
    result = finnhub_client.stock_insider_transactions(
        symbol, from_date_str, to_date_str
    )
    print(f"Full API response for '{symbol}': {result}")
    return result


def get_insider_sentiment(symbol: str, n_days: int = 30) -> list[dict]:
    from_date_str, to_date_str = get_date_range(n_days)
    result = finnhub_client.stock_insider_sentiment(
        symbol, from_date_str, to_date_str
    )
    print(f"Full API response for '{symbol}': {result}")
    return result


def get_sec_filings(symbol: str, n_days: int = 30) -> list[dict]:
    from_date_str, to_date_str = get_date_range(n_days)
    result = finnhub_client.filings(symbol, from_date_str, to_date_str)
    print(f"Full API response for '{symbol}': {result}")
    return result


def get_senate_lobbying(symbol: str, n_days: int = 30) -> list[dict]:
    from_date_str, to_date_str = get_date_range(n_days)
    result = finnhub_client.stock_lobbying(symbol, from_date_str, to_date_str)
    print(f"Full API response for '{symbol}': {result}")
    return result


def get_usa_spending_activity(symbol: str, n_days: int = 30) -> list[dict]:
    from_date_str, to_date_str = get_date_range(n_days)
    result = finnhub_client.stock_usa_spending(
        symbol, from_date_str, to_date_str
    )
    print(f"Full API response for '{symbol}': {result}")
    return result


MODEL = "gemini-2.5-pro"

news_analyst_agent = Agent(
    model=MODEL,
    name="news_analyst_agent",
    instruction=prompt.DATA_ANALYST_PROMPT,
    output_key="news_analysis_output",
    tools=[
        find_symbol,
        get_quote,
        get_company_profile,
        get_company_news,
        find_company_peers,
        get_company_basic_financials,
        get_insider_transactions,
        get_insider_sentiment,
        get_sec_filings,
        get_senate_lobbying,
        get_usa_spending_activity,
    ],
)
