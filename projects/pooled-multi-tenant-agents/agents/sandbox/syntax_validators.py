# Copyright 2026 Google LLC
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

# pylint: disable=line-too-long

"""Deterministic O(N) JavaScript and Bash syntax validators for hermetic sandboxes."""

from __future__ import annotations


def _validate_javascript_syntax(code: str) -> None:
    """Lightweight balanced-delimiter/quote syntax validator for hermetic JavaScript."""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    i = 0
    n = len(code)
    in_quote: str | None = None
    in_block_comment = False
    prev_non_ws = ""
    regex_predecessors = set("([{,;:=!?&|^~+-*%<>")

    while i < n:
        ch = code[i]
        if in_block_comment:
            if code[i : i + 2] == "*/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_quote is not None:
            if ch == "\\":
                i += 2
                continue
            if in_quote == "`" and code[i : i + 2] == "${":
                stack.append("${")
                in_quote = None
                i += 2
                prev_non_ws = "{"
                continue
            if ch == in_quote:
                in_quote = None
                prev_non_ws = ch
                i += 1
                continue
            if ch == "\n" and in_quote in ("'", '"'):
                raise ValueError(
                    "E_SANDBOX_SYNTAX_ERROR: Unterminated JavaScript string literal."
                )
            i += 1
            continue

        if code[i : i + 2] == "//":
            nl = code.find("\n", i + 2)
            i = n if nl == -1 else nl + 1
            continue
        if code[i : i + 2] == "/*":
            in_block_comment = True
            i += 2
            continue
        if ch == "/" and (
            prev_non_ws == "" or prev_non_ws in regex_predecessors
        ):
            j = i + 1
            in_char_class = False
            closed_regex = False
            while j < n and code[j] != "\n":
                rc = code[j]
                if rc == "\\":
                    j += 2
                    continue
                if rc == "[":
                    in_char_class = True
                elif rc == "]":
                    in_char_class = False
                elif rc == "/" and not in_char_class:
                    closed_regex = True
                    j += 1
                    break
                j += 1
            if closed_regex:
                prev_non_ws = "/"
                i = j
                continue

        if ch in ("'", '"', "`"):
            in_quote = ch
        elif ch in ("(", "[", "{"):
            stack.append(ch)
        elif ch in pairs:
            if ch == "}" and stack and stack[-1] == "${":
                stack.pop()
                in_quote = "`"
                i += 1
                continue
            if not stack or stack[-1] != pairs[ch]:
                raise ValueError(
                    f"E_SANDBOX_SYNTAX_ERROR: Unmatched JavaScript delimiter '{ch}'."
                )
            stack.pop()
        if not ch.isspace():
            prev_non_ws = ch
        i += 1

    if in_block_comment or in_quote is not None or stack:
        raise ValueError(
            "E_SANDBOX_SYNTAX_ERROR: Unterminated JavaScript literal, comment, or delimiter."
        )


def _validate_bash_syntax(code: str) -> None:
    """Lightweight balanced-delimiter/quote syntax validator for hermetic Bash."""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    i = 0
    n = len(code)
    in_quote: str | None = None
    in_case = False
    word_buf: list[str] = []

    while i < n:
        ch = code[i]
        if in_quote == "'":
            if ch == "'":
                in_quote = None
            i += 1
            continue
        if in_quote == '"':
            if ch == "\\":
                i += 2
                continue
            if code[i : i + 2] == "$(":
                stack.append("$(")
                in_quote = None
                i += 2
                continue
            if ch == '"':
                in_quote = None
            i += 1
            continue
        if in_quote == "`":
            if ch == "\\":
                i += 2
                continue
            if ch == "`":
                in_quote = None
            i += 1
            continue

        if ch == "\\":
            word_buf.clear()
            i += 2
            continue
        if ch == "#" and (i == 0 or code[i - 1] in " \t\r\n;|&(){}"):
            word_buf.clear()
            nl = code.find("\n", i + 1)
            i = n if nl == -1 else nl + 1
            continue
        if ch.isalnum() or ch == "_":
            word_buf.append(ch)
            i += 1
            continue
        if word_buf:
            word = "".join(word_buf)
            word_buf.clear()
            if word == "case":
                in_case = True
            elif word == "esac":
                in_case = False

        if ch in ("'", '"', "`"):
            in_quote = ch
        elif code[i : i + 2] == "$(":
            stack.append("$(")
            i += 2
            continue
        elif ch in ("(", "[", "{"):
            stack.append(ch)
        elif ch in pairs:
            if ch == ")" and stack and stack[-1] == "$(":
                stack.pop()
                i += 1
                continue
            if ch == ")" and not stack and in_case:
                i += 1
                continue
            if not stack or stack[-1] != pairs[ch]:
                raise ValueError(
                    f"E_SANDBOX_SYNTAX_ERROR: Unmatched Bash delimiter '{ch}'."
                )
            stack.pop()
        i += 1

    if word_buf:
        word = "".join(word_buf)
        if word == "esac":
            in_case = False
    if in_quote is not None or stack:
        raise ValueError(
            "E_SANDBOX_SYNTAX_ERROR: Unterminated Bash quote or unclosed delimiter."
        )
