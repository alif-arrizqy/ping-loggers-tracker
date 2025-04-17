import logging
import os
import psycopg2
from db_utils import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='ping_log_tracker.log'
)
logger = logging.getLogger(__name__)

def check_column_exists(cursor, table_name, column_name):
    """Check if column exists in table"""
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s AND column_name = %s
    """, (table_name, column_name))
    return cursor.fetchone() is not None

def run_migrations():
    """Run database migrations in sequence."""
    logger.info("Starting migration process...")
    
    connection = None
    try:
        # Get DB connection
        connection = Database.get_connection()
        cursor = connection.cursor()
    
        # Migration process
        # logger.info("Add new fields 'length_loggers' to ping_logs table")
        # if not check_column_exists(cursor, 'ping_logs', 'length_loggers'):
        #     cursor.execute("ALTER TABLE ping_logs ADD COLUMN length_loggers INTEGER")
        #     logger.info("Added length_loggers column to ping_logs table")

        # # Commit all changes
        # connection.commit()
        # logger.info("Database migration completed successfully.")
        
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        if connection:
            connection.rollback()
        raise
    finally:
        if connection:
            connection.close()

def create_migration_version_table(cursor):
    """Create a table to track migration versions"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migration_versions (
            id SERIAL PRIMARY KEY,
            version INTEGER NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
    """)

def get_latest_migration_version(cursor):
    """Get the latest applied migration version"""
    try:
        cursor.execute("SELECT MAX(version) FROM migration_versions")
        result = cursor.fetchone()[0]
        return result or 0
    except psycopg2.Error:
        return 0

def apply_migration(cursor, version, description, sql):
    """Apply a migration and record its version"""
    cursor.execute(sql)
    cursor.execute(
        "INSERT INTO migration_versions (version, description) VALUES (%s, %s)",
        (version, description)
    )

if __name__ == "__main__":
    run_migrations()
    logger.info("Migration process completed.")