import subprocess
import os
from datetime import datetime

# Database connection parameters for UAT and Production
# db_config_uat = {
#     'dbname': 'uatsimulab',
#     'user': '',
#     'password': '',
#     'host': 'localhost',
#     'port': '5432'
# }

db_config_prod = {
    'dbname': 'simulab',  # Name of the production database
    'user': '',      # Database user with appropriate permissions
    'password': '',        # Set this to the actual password for the 'ubuntu' user if needed
    'host': 'localhost',   # Change to your production server's IP or hostname if necessary
    'port': '5432'         # Default PostgreSQL port
}


def execute_command(command):
    """Executes a command using subprocess."""
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        raise  # Reraise the exception for handling in the caller

def backup_database(db_config, backup_file):
    """Backs up the database to the specified file."""
    try:
        os.environ['PGPASSWORD'] = db_config['password']

        command = [
            'pg_dump',
            '-U', db_config['user'],
            '-h', db_config['host'],
            '-p', db_config['port'],
            '-F', 'c',  # Custom format
            '-b',  # Include large objects
            '-v',  # Verbose mode
            '-f', backup_file,
            db_config['dbname']
        ]
        
        execute_command(command)
        print(f"Backup of database {db_config['dbname']} completed successfully.")
    
    except Exception as e:
        print(f"An unexpected error occurred during backup: {e}")
    
    finally:
        del os.environ['PGPASSWORD']
def clean_database(db_config):
    """Drops and recreates the database."""
    try:
        os.environ['PGPASSWORD'] = db_config['password']

        # Connect to the 'postgres' database or any existing database
        drop_command = [
            'psql',
            '-U', db_config['user'],
            '-h', db_config['host'],
            '-p', db_config['port'],
            '-d', 'postgres',  # Use 'postgres' as a default database
            '-c', f'DROP DATABASE IF EXISTS {db_config["dbname"]};'
        ]
        execute_command(drop_command)

        # Create the database again
        create_command = [
            'psql',
            '-U', db_config['user'],
            '-h', db_config['host'],
            '-p', db_config['port'],
            '-d', 'postgres',  # Use 'postgres' as a default database
            '-c', f'CREATE DATABASE {db_config["dbname"]};'
        ]
        execute_command(create_command)

        print(f"Database {db_config['dbname']} cleaned and recreated successfully.")

    except Exception as e:
        print(f"An error occurred while cleaning the database: {e}")

    finally:
        del os.environ['PGPASSWORD']

def restore_database(db_config, backup_file):
    """Restores the database from the specified backup file."""
    try:
        os.environ['PGPASSWORD'] = db_config['password']

        command = [
            'pg_restore',
            '--clean',  # Drop the objects before recreating them
            '-U', db_config['user'],
            '-h', db_config['host'],
            '-p', db_config['port'],
            '-d', db_config['dbname'],
            '-v',  # Verbose mode
            backup_file
        ]
        
        execute_command(command)
        print(f"Database {db_config['dbname']} restored successfully from {backup_file}.")
    
    except Exception as e:
        print(f"An unexpected error occurred during restore: {e}")

    finally:
        del os.environ['PGPASSWORD']


# Generate timestamp for the backup file names
timestamp = datetime.now().strftime("%d-%m-%y %H-%M")
backup_file_path_uat = f'./db_backups/{timestamp}_uatdump.dump'
backup_file_path_prod = f'./db_backups/{timestamp}_proddump.dump'

# Backup UAT database
# backup_database(db_config_uat, backup_file_path_uat)

# # Backup Production database
# backup_database(db_config_prod, backup_file_path_prod)

# Clean and Restore UAT database
# restore_file_path_uat = f'./db_backups/04-10-24 12-42_uatdump.dump'
# restore_file_path_prod = f'./db_backups/04-10-24 12-42_proddump.dump'
# clean_database(db_config_uat)
# restore_database(db_config_uat, restore_file_path_uat)

# # Clean and Restore Production database
# clean_database(db_config_prod)
# restore_database(db_config_prod, restore_file_path_prod)
