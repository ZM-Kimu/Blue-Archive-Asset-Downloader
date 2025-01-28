import sqlite3

from lib.structure import DBColumn, DBTable


class TableDatabase:
    def __init__(self, database: str) -> None:
        self.database = database
        self.connection = sqlite3.connect(self.database)

    def __enter__(self) -> "TableDatabase":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.connection.close()

    def get_table_list(self) -> list[str]:
        """Get all table name in database as list.

        Returns:
            list[tuple]: Tables
        """
        cursor = self.connection.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")

        return [table[0] for table in cursor.fetchall() if table]

    def get_table_column_structure(self, table: str) -> list[DBColumn]:
        """Get data structure of table.

        Args:
            table (str): table_name

        Returns:
            list[Column]: A list store all columns structure.
        """
        cursor = self.connection.cursor()

        cursor.execute(f"PRAGMA table_info({table});")

        return [DBColumn(name=col[1], data_type=col[2]) for col in cursor.fetchall()]

    def get_table_data(self, table: str) -> tuple[list, list]:
        """Get all rows and table structure in table.

        Args:
            table (str): table_name

        Returns:
            tuple[list, list]: First list store the column_names. Second list store the rows.
        """
        cursor = self.connection.cursor()

        cursor.execute(f"SELECT * FROM {table};")

        column_names = [description[0] for description in cursor.description]
        rows = cursor.fetchall()

        return column_names, rows

    @staticmethod
    def convert_to_list_dict(table: DBTable) -> list[dict]:
        """Convert table to list of json structure dict.

        Args:
            table (DBTable): Table to convert.

        Returns:
            list[dict]: A list include all the rows to key value pair.
        """
        table_rows = []
        for row in table.data:
            row_data = {}
            for col, value in zip(table.columns, row):
                row_data[col.name] = value
            if row_data:
                table_rows.append(row_data)

        return table_rows
