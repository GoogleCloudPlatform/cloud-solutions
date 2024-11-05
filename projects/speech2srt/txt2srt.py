# -*- coding: utf-8 -*-
#
# Copyright 2020 Google LLC
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

# ruff: noqa

"""Updates existing .srt file with translated lines from .txt files.

Uses an index file (index.csv) to map translated lines to languages.
The index file should be a CSV with the following columns:

Column 1: Original SRT filename
Column 2: Language code (e.g. "fi")
Column 3: Translated SRT filename

For example:

en.srt,fi,fi.srt
en.srt,de,de.srt

This script takes the original SRT file and creates new SRT files for each
translated language.
"""

import argparse
import srt

def load_srt(filename):
    # load original .srt file
    # parse .srt file to list of subtitles
    print("Loading {}".format(filename))
    with open(filename, encoding="utf-8") as f:
        text = f.read()
    return list(srt.parse(text))


def process_translations(subs, indexfile):
    # read index.csv and foreach translated file,

    print("Updating subtitles for each translated language")
    with open(indexfile, encoding="utf-8") as f:
        lines = f.readlines()
    # copy orig subs list and replace content for each line
    for line in lines:
        index_list = line.split(",")
        lang = index_list[1]
        langfile = index_list[2].split("/")[-1]
        lang_subs = update_srt(langfile, subs)
        write_srt(lang, lang_subs)
    return


def update_srt(langfile, subs):
    # change subtitles' content to translated lines

    with open(langfile, encoding="utf-8") as f:
        lines = f.readlines()
    i = 0
    for line in lines:
        subs[i].content = line
        i += 1
    return subs


def write_srt(lang, lang_subs):
    filename = lang + ".srt"
    f = open(filename, "w", encoding="utf-8")
    f.write(srt.compose(lang_subs, strict=True))
    f.close()
    print("Wrote SRT file {}".format(filename))
    return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--srt",
        type=str,
        default="en.srt",
    )
    parser.add_argument(
        "--index",
        type=str,
        default="index.csv",
    )
    args = parser.parse_args()

    subs = load_srt(args.srt)
    process_translations(subs, args.index)


if __name__ == "__main__":
    main()
