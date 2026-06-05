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
# pylint: disable=C0114, C0115, C0301, C0303, C0412, C0413, C0415, E0606, E1136, W0102, W0104, W0311, W0404, W0611, W0612, W0613, W0718, W1203, W1309, W1405, W1510, W1514

import asyncio
import enum
import functools
import inspect
import sys
import time
from typing import Optional

from adk_common.utils.constants import (
    get_optional_env_var,
    get_required_env_var,
)
from google.genai import types

AGENT_VERSION = get_required_env_var("AGENT_VERSION")


class Severity(enum.Enum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


def log_message(message: str, severity: Severity, prefix: Optional[str] = None):
    """Logs a message with a severity and optional prefix.

    Args:
        message: The message to log.
        severity: The severity of the log (DEBUG, INFO, ERROR).
        prefix: Optional prefix. If None, attempts to auto-detect from call stack.
    """
    if prefix is None:
        try:
            # Auto-detect prefix from caller
            frame = inspect.currentframe()
            if frame and frame.f_back:
                caller_frame = frame.f_back

                # Try to get class name
                cls_name = ""
                if "self" in caller_frame.f_locals:
                    cls_name = caller_frame.f_locals["self"].__class__.__name__
                elif "cls" in caller_frame.f_locals:
                    cls_name = caller_frame.f_locals["cls"].__name__

                func_name = caller_frame.f_code.co_name

                if cls_name:
                    prefix = f"{cls_name}.{func_name}"
                else:
                    prefix = func_name
        except Exception:
            prefix = "Unknown"

    formatted_message = f"[{severity.name}]"
    if prefix:
        formatted_message += f" [{prefix}]"

    formatted_message += f" [{AGENT_VERSION}]"
    formatted_message += f" {message}"

    if severity == Severity.ERROR:
        print(formatted_message, file=sys.stderr)
    else:
        print(formatted_message, file=sys.stdout)


from google.genai import types

# Set this to a positive value to truncate long strings in logs
MAX_LOG_STRING_LENGTH = 0


def sanitize_arg(arg):
    """Sanitizes arguments for logging, redacting bytes and large objects."""
    if isinstance(arg, list):
        return [sanitize_arg(item) for item in arg]
    if isinstance(arg, tuple):
        return tuple(sanitize_arg(item) for item in arg)
    if isinstance(arg, dict):
        return {k: sanitize_arg(v) for k, v in arg.items()}

    res = arg
    if isinstance(arg, bytes):
        res = f"<bytes: {len(arg)} bytes>"
    elif isinstance(arg, types.Part):
        if arg.inline_data:
            res = f"<Part: inline_data redacted, mime_type={arg.inline_data.mime_type}>"
        elif arg.file_data:
            res = f"<Part: file_data uri={arg.file_data.file_uri}>"
    elif "ToolContext" in str(type(arg)):
        res = "<ToolContext>"
    elif "google.genai.client.Client" in str(type(arg)):
        res = "<GenAI Client>"
    elif not isinstance(arg, (str, int, float, bool, type(None))):
        res = f"<{type(arg).__name__} object>"

    if MAX_LOG_STRING_LENGTH > 0:
        res_str = str(res)
        if len(res_str) > MAX_LOG_STRING_LENGTH:
            return res_str[:MAX_LOG_STRING_LENGTH] + "..."
    return res


def log_function_call(func):
    """Decorator to log function calls and arguments with execution time."""
    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            sanitized_args = sanitize_arg(args)
            sanitized_kwargs = sanitize_arg(kwargs)
            log_message(
                f"Calling async function: {func.__name__}. Arguments: {sanitized_args}, {sanitized_kwargs}",
                Severity.DEBUG,
            )
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                log_message(
                    f"Finished async function: {func.__name__}. Duration: {duration:.4f}s",
                    Severity.INFO,
                )

        return async_wrapper
    else:

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            sanitized_args = sanitize_arg(args)
            sanitized_kwargs = sanitize_arg(kwargs)
            log_message(
                f"Calling sync function: {func.__name__}. Arguments: {sanitized_args}, {sanitized_kwargs}",
                Severity.DEBUG,
            )
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                log_message(
                    f"Finished sync function: {func.__name__}. Duration: {duration:.4f}s",
                    Severity.INFO,
                )

        return sync_wrapper
