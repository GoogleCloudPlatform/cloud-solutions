#!/usr/bin/env python
#  Copyright 2024 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Dataflow template to copy batch data from GCS to AlloyDB."""

import argparse
import io
import logging
import re
from typing import Iterable, Mapping, Tuple

import apache_beam as beam
import apache_beam.dataframe.convert as dataframe_convert
from apache_beam.io import avroio
from apache_beam.io import jdbc
from apache_beam.options import pipeline_options
from apache_beam.io.gcp import gcsio
from google.cloud import storage
from google.api_core.client_info import ClientInfo
import pandas


# Used to format some data as CSV without interfering with the data.
_CUSTOM_DELIMITER = ';;;;'


def _assert_files_exist(input_pattern: str):
    """Validates and asserts that there are files on the GCS file pattern.

    Args:
        input_pattern: file pattern glob to validate.

    Raises:
        ValueError: if files do not match.
    """
    scheme = input_pattern.split('://')[0]
    if scheme != 'gs':
        return  # Only Cloud Storage paths are validated.

    # Raises ValueError if not a valid gs:// path.
    bucket_name, object_pattern = gcsio.parse_gcs_path(input_pattern)

    object_parts = object_pattern.split('/')
    for i in range(len(object_parts)):
        if re.compile(r'[^a-zA-Z-_]').search(object_parts[i]):
            break

    prefix = '/'.join(object_parts[:i])
    match_glob = '/'.join(object_parts[i:])
    if prefix and match_glob:
        prefix += '/'

    gcs_client = storage.Client(
        client_info=ClientInfo(
            user_agent='cloud-solutions/dataflow-gcs-to-alloydb-v1'
        )
    )
    files = gcs_client.bucket(bucket_name=bucket_name).list_blobs(
        prefix=prefix,
        match_glob=match_glob,
        max_results=1,  # Only need to know that there is at least one file.
    )

    if not files:
        raise ValueError(f'No files matching pattern: {input_pattern}')


def _convert_input_schema_to_field_tuples(
    input_schema: str,
) -> Iterable[Tuple[str, str]]:
    """Converts the input schema into a list of tuples.

    Args:
      input_schema: Input schema in field1:type1,field2:type2 format.

    Returns:
      List of fields in [(field_name, field_type)] format.
    """
    field_string_list = input_schema.split(';')
    field_pairs = [
        tuple(field_string.split(':')) for field_string in field_string_list
    ]
    return field_pairs


def _convert_input_schema_to_columns(input_schema: str) -> Iterable[str]:
    """Converts the input schema into columns.

    Args:
      input_schema: Input schema in field1:type1,field2:type2 format.

    Returns:
      List of fields in ['field'] format.
    """
    field_list = _convert_input_schema_to_field_tuples(input_schema)
    return [field_name for (field_name, _) in field_list]


def _convert_input_schema_to_dtypes(input_schema: str) -> Mapping[str, str]:
    """Converts the input schema into dtypes for pandas DataFrame.

    Args:
      input_schema: Input schema in field1:type1,field2:type2 format.

    Returns:
      Dtypes in {'field': 'type'} format.
    """
    field_list = _convert_input_schema_to_field_tuples(input_schema)
    return {field_name: field_type for (field_name, field_type) in field_list}


def _row_dict_to_dataframe(
    data_dict: dict,
    df_columns: Iterable[str],
    df_dtypes: Mapping[str, str],
) -> pandas.DataFrame:
    """Converts the dict of row data into a dataframe with schema.

    Args:
      data_text: Data in dict format. Example: {'field1': 1}.
      df_columns: List of columns in order. Example: ['field1', 'field2'].
      df_dtypes: Map of fields and types. Example: {'field1': 'string'}.

    Returns:
      A pandas DataFrame with the row of data and the right schema.
    """
    data_as_csv = _CUSTOM_DELIMITER.join(
        [str(data_dict[column_name]) for column_name in df_columns]
    )
    return _row_list_to_dataframe(
        data_text=data_as_csv,
        delimiter=_CUSTOM_DELIMITER,
        df_columns=df_columns,
        df_dtypes=df_dtypes,
    )


def _row_list_to_dataframe(
    data_text: str,
    delimiter: str,
    df_columns: Iterable[str],
    df_dtypes: Mapping[str, str],
) -> pandas.DataFrame:
    """Converts the list of data into a dataframe with schema.

    Args:
      data_text: Row data in text format. Example: 'a,1'].
      delimiter: CSV separator in string format. Example: ','.
      df_columns: List of columns in order. Example: ['field1', 'field2'].
      df_dtypes: Map of fields and types. Example: {'field1': 'string'}.

    Returns:
      A pandas DataFrame with the row of data and the right schema.
    """
    return pandas.read_csv(
        io.StringIO(data_text),
        sep=delimiter,
        engine='python',
        dtype=df_dtypes,
        names=df_columns,
    )


def _validate_pipeline_options(static_args):
    """Validates pipeline options.

    Args:
      static_args: Static arguments for the pipeline.
    """
    _assert_files_exist(static_args.input_file_pattern)


def run(argv=None, save_main_session=True):
    """Reads data from GCS and writes it to an AlloyDB database."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--input_file_pattern',
        required=True,
        help=(
            'File path or pattern to the file(s). '
            'Example: e.g. gs://bucket/path/*.csv'
        ),
    )
    parser.add_argument(
        '--input_file_contains_headers',
        type=int,
        required=False,  # Optional, used when using input_file_format=csv.
        default=1,
        choices=[0, 1],
        help=(
            'Whether the input CSV files contain a header record. '
            'Use 1 for true and 0 for false. '
            'Only used for CSV files. '
            'Defaults to 1 (true).'
        ),
    )
    parser.add_argument(
        '--input_file_format',
        required=True,
        help=('Source file format. Supported: avro, csv.'),
        choices=['csv', 'avro'],
    )
    parser.add_argument(
        '--input_schema',
        dest='input_schema',
        required=True,
        help=(
            'The input schema using dtype strings. '
            'The format for each field is `field_name:dtype`. '
            'The fields must follow the order of the file when in csv format. '
            'Each field must be separated with `;`. '
            'Example: `name:string;phone:number`.',
        ),
    )
    parser.add_argument(
        '--input_csv_file_delimiter',
        dest='input_csv_file_delimiter',
        # Optional, used when using input_file_format=csv.
        default=',',
        help=(
            'The column delimiter for the input CSV file (e.g. ","). '
            'Only used for CSV files.'
        ),
    )

    parser.add_argument(
        '--alloydb_ip',
        dest='alloydb_ip',
        default='127.0.0.1',
        help='IP of the AlloyDB instance (e.g. 10.3.125.7)',
    )
    parser.add_argument(
        '--alloydb_port',
        dest='alloydb_port',
        default='5432',
        help='Port of the AlloyDB instance (e.g. 5432)',
    )
    parser.add_argument(
        '--alloydb_database',
        dest='alloydb_database',
        default='postgres',
        help='Name of the AlloyDB database (e.g. postgres)',
    )
    parser.add_argument(
        '--alloydb_user',
        dest='alloydb_user',
        default='postgres',
        help='User to login to Postgres/AlloyDB database',
    )
    parser.add_argument(
        '--alloydb_password',
        dest='alloydb_password',
        help='Password of the Postgres/AlloyDB user to login',
    )
    parser.add_argument(
        '--alloydb_table',
        dest='alloydb_table',
        required=True,
        help='Name of the Postgres/AlloyDB table',
    )

    static_args, pipeline_args = parser.parse_known_args(argv)

    pipeline_opts = pipeline_options.PipelineOptions(pipeline_args)
    pipeline_opts.view_as(pipeline_options.SetupOptions).save_main_session = (
        save_main_session
    )

    _validate_pipeline_options(static_args)

    df_columns = _convert_input_schema_to_columns(static_args.input_schema)
    df_dtypes = _convert_input_schema_to_dtypes(static_args.input_schema)
    df_proxy = pandas.DataFrame(columns=df_columns).astype(df_dtypes)

    with beam.Pipeline(options=pipeline_opts) as p:
        if static_args.input_file_format == 'csv':
            df_rows = (
                p
                | 'Read CSV File'
                >> beam.io.ReadFromText(
                    static_args.input_file_pattern,
                    skip_header_lines=(static_args.input_file_contains_headers),
                )
                | 'Convert Row to DataFrame'
                >> beam.Map(
                    _row_list_to_dataframe,
                    delimiter=static_args.input_csv_file_delimiter,
                    df_columns=df_columns,
                    df_dtypes=df_dtypes,
                )
            )
        elif static_args.input_file_format == 'avro':
            df_rows = (
                p
                | 'Read Avro File'
                >> avroio.ReadFromAvro(
                    static_args.input_file_pattern,
                    as_rows=False,
                )
                | 'Convert Row to DataFrame'
                >> beam.Map(
                    _row_dict_to_dataframe,
                    df_columns=df_columns,
                    df_dtypes=df_dtypes,
                )
            )
        else:
            raise ValueError('File input format must be csv or avro.')

        data_rows = (
            df_rows
            | 'Convert DataFrame to row with BeamSchema'
            >> beam.ParDo(
                dataframe_convert.DataFrameToRowsFn(
                    proxy=df_proxy,
                    include_indexes=False,
                )
            )
        )

        _ = data_rows | 'Write to AlloyDB' >> jdbc.WriteToJdbc(
            driver_class_name='org.postgresql.Driver',
            table_name=static_args.alloydb_table,
            jdbc_url=(
                'jdbc:postgresql://'
                f'{static_args.alloydb_ip}:'
                f'{static_args.alloydb_port}/'
                f'{static_args.alloydb_database}'
            ),
            username=static_args.alloydb_user,
            password=static_args.alloydb_password,
            connection_properties='stringtype=unspecified',
        )


if __name__ == '__main__':
    logger = logging.getLogger().setLevel(logging.INFO)
    run()
