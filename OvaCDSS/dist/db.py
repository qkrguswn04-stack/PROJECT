# from sqlalchemy import create_engine, MetaData, Table
# from sqlalchemy.dialects.postgresql import insert
# from config import DB_SHAPE
# import pandas as pd
# import numpy as np


# metadata = MetaData()
# db_nm = DB_SHAPE['db_url']
# schema_nm = DB_SHAPE['schema']
# table_nm = DB_SHAPE['table']
# conn = create_engine(db_nm)
# table = Table(table_nm, metadata, autoload_with = conn, schema = schema_nm)

# def upsert_method(table, conn, keys, data_iter):
#     sql_insert = insert(table.table).values(list(data_iter))
#     upsert_stmt = sql_insert.on_conflict_do_nothing(index_elements=['subject_id'])
#     conn.execute(upsert_stmt)

# def data_save(df):
#     engine = create_engine(db_nm)
#     try:
#         df.to_sql(
#             con=engine,                     # The connection engine
#             schema=schema_nm,      # Name of the SQL schema
#             name=table_nm,                     # Name of the SQL table
#             if_exists='append',             # Options: 'fail', 'replace', 'append'
#             index=False,                    # Don't save the DataFrame index as a column
#             chunksize=1000,                 # Useful for very large datasets
#             method=upsert_method            # Speeds up performance for larger inserts
#         )
#         print("Data saved successfully!")
        
#     except Exception as e:
#         print(f"Error saving to database: {e}")

import psycopg2
from psycopg2 import sql

def connect_to_linux_db():
    try:
        # Define your connection parameters
        connection = psycopg2.connect(
            host="192.168.0.17",  # Your Linux machine's IP
            database="mimic",
            user="team2",
            password="5inyoung", # The password you set for team2
            port="5432"
        )
        print("Successfully connected to the Linux database!")
        return connection
    except Exception as e:
        print(f"Failed to connect: {e}")
        return None

def save_data(df):
    conn = connect_to_linux_db()
    if conn:
        try:
            cur = conn.cursor()
            # method 1: Explicitly defining the schema and table
            # We omit 'id' because it is GENERATED ALWAYS AS IDENTITY
            query = sql.SQL("INSERT INTO {schema}.{table} (name) VALUES (%s) RETURNING id").format(
                schema=sql.Identifier('mimic_ova'),
                table=sql.Identifier('patient')
            )
            
            cur.execute(query, (df,))
            new_id = cur.fetchone()[0]
            
            conn.commit()
            print(f"Data saved! Assigned ID: {new_id}")
            
        except Exception as e:
            print(f"Execution error: {e}")
        finally:
            cur.close()
            conn.close()

if __name__ == '__main__':

    # Execute the logic
    save_data("pph")