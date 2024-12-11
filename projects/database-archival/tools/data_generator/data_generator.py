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

"""Generates SQL dumps for demo purposes.

The current syntax is for Cloud SQL for MySQL.
"""

import random
import re
import string

# Number of rows to generate.
USER_NUM_ROWS = 100
TRANSACTIONS_NUM_ROWS = 100_000

_SQL_DUMP_FILE = 'mysql_sqldump.sql'
_TABLE_SCHEMA = """
DROP TABLE IF EXISTS `Transaction`;
DROP TABLE IF EXISTS `User`;

CREATE TABLE `User` (
  `user_id` INT NOT NULL,
  `user_name` VARCHAR(100) NOT NULL,
  PRIMARY KEY (`user_id`)
);

CREATE TABLE `Transaction` (
  `transaction_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  `transaction_date` DATE NOT NULL,
  `amount` FLOAT NOT NULL,
  PRIMARY KEY (`transaction_id`),
  FOREIGN KEY (`user_id`)
    REFERENCES `User` (`user_id`)
);
"""


def _generate_user_insert_statement() -> str:
    """Generates the SQL statement to insert values into the User table.

    Returns:
        SQL statement to insert values in the User table.
    """
    user_contents = []
    for i in range(USER_NUM_ROWS):
        name_length = random.randint(5, 50)
        user_name = (
            re.sub(
                ' +',
                ' ',
                ''.join(
                    random.choices(string.ascii_lowercase + ' ', k=name_length)
                ),
            )
            .strip()
            .capitalize()
        )
        user_contents.append(f'  ({i + 1}, "{user_name}")')
    return '\n'.join(
        [
            'INSERT INTO `User` (`user_id`, `user_name`)',
            'VALUES',
            ',\n'.join(user_contents),
            ';',
        ]
    )


def _generate_transaction_insert_statement() -> str:
    """Generates the SQL statement to insert values into the User table.

    Returns:
        SQL statement to insert values in the Transaction table.
    """
    transaction_contents = []
    for i in range(TRANSACTIONS_NUM_ROWS):
        user_id = random.randint(1, USER_NUM_ROWS)
        days_ago = (i + 1) % 3650  # Limit up to 10 years ago.
        transaction_date = f'DATE_ADD(CURRENT_DATE(), INTERVAL -{days_ago} DAY)'
        amount = round(random.uniform(1, 100), 2)
        transaction_contents.append(
            f'  ({i + 1}, {user_id}, {transaction_date}, {amount})'
        )
    return '\n'.join(
        [
            'INSERT INTO `Transaction` (',
            '  `transaction_id`, `user_id`, `transaction_date`, `amount`',
            ')',
            'VALUES',
            ',\n'.join(transaction_contents),
            ';',
        ]
    )


def generate_sql_dump():
    """Generates a SQL dump file that can be loaded into Cloud SQL for MySQL."""
    with open(_SQL_DUMP_FILE, 'w', encoding='utf-8') as f:
        f.write(
            '\n\n'.join(
                [
                    _TABLE_SCHEMA,
                    _generate_user_insert_statement(),
                    _generate_transaction_insert_statement(),
                ]
            )
        )


if __name__ == '__main__':
    generate_sql_dump()
