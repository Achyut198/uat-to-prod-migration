import psycopg2
import pandas as pd
import os
import numpy as np
from backupDumpAndRestoreDb import backup_database
from datetime import datetime
# Database connection parameters for UAT and Production
db_config_uat = {
    'dbname': 'uatsimulab',
    'user': '',
    'password': '',
    'host': 'localhost',
    'port': '5432'
}

# db_config_prod = {
#     'dbname': 'simulab',  # Name of the production database
#     'user': '',      # Database user with appropriate permissions
#     'password': '',        # Set this to the actual password for the 'ubuntu' user if needed
#     'host': 'localhost',   # Change to your production server's IP or hostname if necessary
#     'port': '5432'         # Default PostgreSQL port
# }


# Database connection setup
def create_connection(config):
    try:
        conn = psycopg2.connect(**config)
        return conn
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None

# Disable all foreign key constraints for the specified tables
def disable_all_constraints(conn, tables):
    cur = conn.cursor()
    for table in tables:
        cur.execute(f"ALTER TABLE {table} DISABLE TRIGGER ALL;")
    conn.commit()
    print('disable all constraints')

# Enable all foreign key constraints for the specified tables
def enable_all_constraints(conn, tables):
    cur = conn.cursor()
    for table in tables:
        cur.execute(f"ALTER TABLE {table} ENABLE TRIGGER ALL;")
    conn.commit()
    print('enable all constraints')

# Fetch table data from UAT and store it in a CSV file
def backup_table_to_csv(conn, table_name, backup_folder):
    query = f"SELECT * FROM {table_name};"
    data = pd.read_sql(query, conn)
    
    # Store the data as a CSV file
    csv_file = os.path.join(backup_folder, f"{table_name}.csv")
    data.to_csv(csv_file, index=False)
    print(f"Backup completed for table: {table_name}, stored in {csv_file}")


# Backup all tables to CSV files
def backup_to_csv(uat_config, tables, backup_folder):
    # Create backup folder if it doesn't exist
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    # Connect to UAT database
    uat_conn = create_connection(uat_config)
    if not uat_conn:
        return
    
    try:
        # Process each table
        for table in tables:
            backup_table_to_csv(uat_conn, table, backup_folder)
        
        print("Backup process completed successfully!")
    
    except Exception as e:
        print(f"Error during backup: {e}")
    
    finally:
        uat_conn.close()


# Tables to backup and restore
TABLES = ['simulab_school', 'school_department', 'school_standard', 
          'simulab_course', 'simulab_experiment', 'experiment_quiz', 'quiz_question', 'quiz_answer','simulab_experiment_rel','simulab_experiment_object','simulab_experiment_link','simulab_experiment_line','simulab_course_view','quiz_answer','quiz_image_model','quiz_question','ir_act_server','ir_act_server_group_rel','ir_act_url','ir_act_window','ir_actions','ir_actions_todo','ir_asset','ir_attachment','ir_config_parameter','simulab_course_view_line','rel_experiment_quiz_tag','exam_marks_simulab_experiment_rel']

# Backup and Restore directories
BACKUP_FOLDER = "db_backups"

# Backup data from UAT to CSV
backup_to_csv(db_config_uat, TABLES, BACKUP_FOLDER)
timestamp = datetime.now().strftime("%d-%m-%y %H-%M")
backup_file_path_uat = f'./db_backups/{timestamp}_uatdump.dump'
backup_file_path_prod = f'./db_backups/{timestamp}_proddump.dump'

backup_database(db_config_uat, backup_file_path_uat)

# # Backup Production database
# backup_database(db_config_prod, backup_file_path_prod)






# Update image URLs in specified tables
def update_image_urls(conn, tables, old_url, new_url):
    cur = conn.cursor()
    for table in tables:
        try:
            query = f"""
                UPDATE {table}
                SET image_url = REPLACE(image_url, %s, %s)
                WHERE image_url LIKE %s;
            """
            cur.execute(query, (old_url, new_url, f"{old_url}%"))
            print(f"Updated image URLs in table: {table}")
        except Exception as e:
            print(f"Error updating URLs in table {table}: {e}")
    conn.commit()

def callToUpdateUrls():
    URL_UPDATE_TABLES = [  
            'simulab_course', 'simulab_experiment', 'experiment_quiz','simulab_experiment_object','quiz_answer','quiz_image_model','quiz_question'
        ]
        
    old_image_url = 'http://ec2-18-214-233-182.compute-1.amazonaws.com:8169'
    new_image_url = 'http://localhost:8070'

    prod_conn = create_connection(db_config_prod)
    if prod_conn:
        update_image_urls(prod_conn, URL_UPDATE_TABLES, old_image_url, new_image_url)
        prod_conn.close()

 

# Get columns dynamically from the table schema
def get_table_columns(conn, table_name):
    query = f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position;
    """
    cur = conn.cursor()
    cur.execute(query)
    columns = [(row[0], row[1]) for row in cur.fetchall()]  # Return both column name and data type
    return columns

# Handle NaN and type casting for date and other types
def handle_nan_values(row, columns):
    new_row = []
    for (col_name, col_type), value in zip(columns, row):
        if pd.isna(value):
            # Handle NaN values according to the data type
            if col_type in ['date', 'timestamp without time zone']:
                new_row.append(None)  # Set NULL for date columns
            elif col_type in ['integer', 'bigint', 'smallint', 'numeric', 'real', 'double precision']:
                new_row.append(None)  # Set NULL for numeric types
            else:
                new_row.append(None)  # Set NULL for other types as well
        else:
            # Convert numpy types to native Python types
            if isinstance(value, np.integer):
                new_row.append(int(value))  # Convert numpy integer to Python int
            elif isinstance(value, float):  # Check for Python float
                new_row.append(float(value))  # Ensure it's a float
            else:
                new_row.append(value)  # For other types, append as is
    return new_row

# Read the CSV file and upsert the data into the Production database
def restore_table_from_csv(conn, table_name, csv_file, key):
    # Load data from CSV
    print(f'restoring from table {table_name}')
    data = pd.read_csv(csv_file)
    columns = get_table_columns(conn, table_name)  # Get columns and their types dynamically

    col_names = [col[0] for col in columns]  # List of column names
    cur = conn.cursor()

    # Create a mapping of column names to their types for dynamic conversion
    col_type_map = {col[0]: col[1] for col in columns}
    alreadySearcherKey =[]
    for _, row in data.iterrows():
        row_values = handle_nan_values(row.values, columns)  # Handle NaN and data types

        # Convert row values dynamically based on the column types
        row_values = [
            (int(value) if col_type_map[col_names[i]] in ['integer', 'bigint', 'smallint'] and isinstance(value, (np.integer, np.int64)) else 
             float(value) if col_type_map[col_names[i]] in ['real', 'double precision'] and isinstance(value, float) else 
             value)
            for i, value in enumerate(row_values)
        ]

        col_str = ', '.join([f'"{col}"' for col in col_names])  # Quote column names
        placeholders = ', '.join(['%s'] * len(col_names))  # Placeholders for values
        update_str = ', '.join([f'"{col}" = %s' for col in col_names])  # Update columns

        # Get the key value for existence check, converting it based on the column type
        key_value = row_values[col_names.index(key)]
        key_type = col_type_map[key]

        # Convert key_value to the appropriate type if necessary
        if key_type in ['integer', 'bigint', 'smallint'] and isinstance(key_value, (np.integer, np.int64)):
            key_value = int(key_value)
        elif key_type in ['real', 'double precision'] and isinstance(key_value, float):
            key_value = float(key_value)

        # Check if the record exists
        query = f"SELECT COUNT(*) FROM {table_name} WHERE {key} = %s;"
        cur.execute(query, (key_value,))
        exists = cur.fetchone()[0]
        if exists >1:
            if key_value not  in alreadySearcherKey:
                delete_query = f"DELETE FROM {table_name} WHERE {key} = %s;"
                cur.execute(delete_query, (row_values[col_names.index(key)],))
            alreadySearcherKey.append(key_value)
            insert_query = f"""
                INSERT INTO {table_name} ({col_str})
                VALUES ({placeholders});
            """
            cur.execute(insert_query, tuple(row_values))
        elif exists ==1 and  key_value not  in alreadySearcherKey:
            # If record exists, perform update
            alreadySearcherKey.append(key_value)
            update_query = f"""
                UPDATE {table_name} SET {update_str}
                WHERE {key} = %s;
            """
            updateData = (*row_values, key_value)
            cur.execute(update_query, updateData)  # Pass column values and the primary key
            conn.commit()
        else:
            # If record does not exist, perform insert
            insert_query = f"""
                INSERT INTO {table_name} ({col_str})
                VALUES ({placeholders});
            """
            cur.execute(insert_query, tuple(row_values))  # Pass the column values dynamically
            conn.commit()
    
    conn.commit()
    print(f"Restore completed for table: {table_name} from {csv_file}")
    
# Restore all tables from CSV files
def restore_from_csv(prod_config, TABLESOBJ, backup_folder):
    # Connect to Production database
    tables = TABLESOBJ.get("TABLES",[])
    key = TABLESOBJ.get("key","id")
    prod_conn = create_connection(prod_config)
    if not prod_conn:
        return
    
    try:
        # Disable foreign key constraints for all specified tables
        disable_all_constraints(prod_conn, tables)

        # Process each table
        for table in tables:
            csv_file = os.path.join(backup_folder, f"{table}.csv")
            if os.path.exists(csv_file):
                restore_table_from_csv(prod_conn, table, csv_file,key)
            else:
                print(f"CSV file not found for table: {table}")
        
        # Enable foreign key constraints for all specified tables
        enable_all_constraints(prod_conn, tables)
        callToUpdateUrls()
        print("Restore process completed successfully!")
    
    except Exception as e:
        print(f"Error during restore: {e}")
    
    finally:
        prod_conn.close()

# Tables to backup and restore
# Tables to backup and restore
# Tables to backup and restore
TABLESOBJ = {"key":"id","TABLES":['simulab_school', 'school_department', 'school_standard', 
          'simulab_course', 'simulab_experiment', 'experiment_quiz', 'quiz_question', 'quiz_answer','simulab_experiment_object','simulab_experiment_link','simulab_experiment_line','simulab_course_view','quiz_answer','quiz_image_model','quiz_question','simulab_course_view_line']}


# Backup and Restore directories
BACKUP_FOLDER = "db_backups"

# Restore data from CSV to Production
# restore_from_csv(db_config_prod, TABLESOBJ, BACKUP_FOLDER)
TABLESOBJ = {"key":"id","TABLES":['ir_act_server','ir_act_url','ir_actions','ir_actions_todo','ir_asset','ir_attachment']}
# restore_from_csv(db_config_prod, TABLESOBJ, BACKUP_FOLDER)
TABLESOBJ = {"key":"course_id","TABLES":['simulab_experiment_rel']}
# restore_from_csv(db_config_prod, TABLESOBJ, BACKUP_FOLDER)
TABLESOBJ = {"key":"act_id","TABLES":['ir_act_server_group_rel']}
# restore_from_csv(db_config_prod, TABLESOBJ, BACKUP_FOLDER)
TABLESOBJ = {"key":"quiz_id","TABLES":['rel_experiment_quiz_tag']}
# restore_from_csv(db_config_prod, TABLESOBJ, BACKUP_FOLDER)
TABLESOBJ = {"key":"exam_id","TABLES":['exam_marks_simulab_experiment_rel']}
# restore_from_csv(db_config_prod, TABLESOBJ, BACKUP_FOLDER)
