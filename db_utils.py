import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

logger = logging.getLogger(__name__)

# Database connection parameters
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'ping_logs_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

class Database:
    @staticmethod
    def get_connection():
        """Get a connection to the PostgreSQL database."""
        try:
            connection = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            return connection
        except Exception as e:
            logger.error(f"Error connecting to the database: {e}")
            raise
    
    @staticmethod
    def create_tables():
        """Create necessary tables if they don't exist"""
        connection = None
        try:
            connection = Database.get_connection()
            cursor = connection.cursor()
            
            # Create ping_logs table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ping_logs (
                id SERIAL PRIMARY KEY,
                timestamp VARCHAR(50) NOT NULL,
                pr_code VARCHAR(10) NOT NULL,
                site_name VARCHAR(50) NOT NULL,
                ip_address VARCHAR(15) NOT NULL,
                ping_success BOOLEAN,
                ping_time_ms INTEGER,
                length_loggers INTEGER
            )
            ''')
            
            # Create a unique constraint for ip_address and timestamp
            try:
                cursor.execute('''
                ALTER TABLE ping_logs 
                ADD CONSTRAINT unique_ip_timestamp UNIQUE (ip_address, timestamp)
                ''')
                logger.info("Added unique constraint on ip_address and timestamp")
            except psycopg2.errors.DuplicateTable:
                # Constraint already exists
                connection.rollback()
            except Exception as e:
                logger.warning(f"Could not add unique constraint: {e}")
                connection.rollback()
            
            # Create index for faster queries
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ping_logs_ip_timestamp 
            ON ping_logs(ip_address, timestamp)
            ''')
            
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ping_logs_pr_code 
            ON ping_logs(pr_code)
            ''')
            
            connection.commit()
            logger.info("Database tables created successfully")
        except psycopg2.Error as e:
            logger.error(f"Error creating tables: {e}")
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                connection.close()
    
    @staticmethod
    def insert_ping_log(timestamp, pr_code, site_name, ip_address, battery_version, ping_success, ping_time_ms):
        """
        Insert or update ping log data based on pr_code
        - If pr_code doesn't exist, insert a new record
        - If pr_code exists, update the existing record
        """
        connection = None
        try:
            connection = Database.get_connection()
            cursor = connection.cursor()
            
            # Check if the pr_code already exists
            cursor.execute(
                "SELECT id from ping_logs WHERE pr_code = %s LIMIT 1",
                (pr_code,)
            )
            existing_record = cursor.fetchone()
            
            if existing_record:
                # PR code exists, update the existing record
                cursor.execute('''
                UPDATE ping_logs 
                SET 
                    ip_address = %s, 
                    site_name = %s, 
                    timestamp = %s, 
                    battery_version = %s,
                    ping_success = %s, 
                    ping_time_ms = %s
                WHERE pr_code = %s
                ''', (ip_address, site_name, timestamp, battery_version, ping_success, ping_time_ms, pr_code))
                
                logger.info(f"Updated existing record for PR code: {pr_code}")
            else:
                # PR code doesn't exist, insert a new record
                cursor.execute('''
                INSERT INTO ping_logs (timestamp, pr_code, site_name, ip_address, ping_success, ping_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s)
                ''', (timestamp, pr_code, site_name, ip_address, ping_success, ping_time_ms))
                
                logger.info(f"Inserted new record for PR code: {pr_code}")
            
            connection.commit()
            return True
        except psycopg2.Error as e:
            logger.error(f"Error handling ping log for PR code {pr_code}: {e}")
            if connection:
                connection.rollback()
            return False
        finally:
            if connection:
                connection.close()
    
    @staticmethod
    def get_ping_logs(limit=100, offset=0, site_name=None):
        """Get ping logs with optional filtering"""
        connection = None
        try:
            connection = Database.get_connection()
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            
            # Build query with optional filters
            query = "SELECT timestamp, pr_code, site_name, ip_address, battery_version, ping_success, ping_time_ms FROM ping_logs"
            params = []
            
            conditions = []
            if site_name:
                conditions.append("site_name = %s")
                params.append(site_name)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                
            query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return cursor.fetchall()
        except psycopg2.Error as e:
            logger.error(f"Error fetching ping logs: {e}")
            return []
        finally:
            if connection:
                connection.close()

    @staticmethod
    def insert_length_loggers(pr_code, site_name, ip_address, length_loggers):
        """
        Insert or update length loggers data based on pr_code
        """
        connection = None
        try:
            connection = Database.get_connection()
            cursor = connection.cursor()
            
            # Check if the ip_address and pr_code already exists
            cursor.execute(
                "SELECT id FROM ping_logs WHERE pr_code = %s LIMIT 1",
                (pr_code,)
            )
            existing_record = cursor.fetchone()
            
            if existing_record:
                # Record exists, update the existing record
                cursor.execute('''
                UPDATE ping_logs 
                SET length_loggers = %s 
                WHERE pr_code = %s
                ''', (length_loggers, pr_code))
                
                logger.info(f"Updated length loggers for Site: {site_name} and PR code: {pr_code}")
            else:
                # Record doesn't exist, insert a new record
                cursor.execute('''
                INSERT INTO ping_logs (pr_code, site_name, ip_address, length_loggers)
                VALUES (%s, %s, %s)
                ''', (pr_code, site_name, ip_address, length_loggers))
                
                logger.info(f"Inserted new length loggers for Site: {site_name} and PR code: {pr_code}")
            
            connection.commit()
            return True
        except psycopg2.Error as e:
            logger.error(f"Error handling length loggers for Site: {site_name}: {e}")
            if connection:
                connection.rollback()
            return False
        finally:
            if connection:
                connection.close()

    @staticmethod
    def get_length_loggers(limit=100, offset=0, site_name=None):
        """Get ping logs with optional filtering"""
        connection = None
        try:
            connection = Database.get_connection()
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            
            # Build query with optional filters
            query = "SELECT timestamp, pr_code, site_name, ip_address, battery_version, length_loggers FROM ping_logs"
            params = []
            
            conditions = []
            if site_name:
                conditions.append("site_name = %s")
                params.append(site_name)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                
            query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return cursor.fetchall()
        except psycopg2.Error as e:
            logger.error(f"Error fetching ping logs: {e}")
            return []
        finally:
            if connection:
                connection.close()

    @staticmethod
    def get_summary(hours=24):
        """
        Get a summary of ping logs for the last specified hours
        
        Args:
            hours (int): Number of hours to look back for the summary
            
        Returns:
            dict: Summary statistics
        """
        connection = None
        try:
            connection = Database.get_connection()
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            
            # Get the timestamp for X hours ago
            time_ago = datetime.now() - timedelta(hours=hours)
            time_ago_str = time_ago.strftime('%Y-%m-%d %H:%M:%S')
            
            # Get total unique sites
            cursor.execute("""
                SELECT COUNT(DISTINCT pr_code) AS total_sites
                FROM ping_logs
                WHERE timestamp >= %s
            """, (time_ago_str,))
            
            result = cursor.fetchone()
            total_sites = result['total_sites'] if result else 0
            
            # Get number of sites currently up (based on most recent ping)
            cursor.execute("""
                WITH recent_pings AS (
                    SELECT 
                        pr_code,
                        ping_success,
                        ROW_NUMBER() OVER (PARTITION BY pr_code ORDER BY timestamp DESC) AS rn
                    FROM ping_logs
                    WHERE timestamp >= %s
                )
                SELECT COUNT(*) AS sites_up
                FROM recent_pings
                WHERE rn = 1 AND ping_success = TRUE
            """, (time_ago_str,))
            
            result = cursor.fetchone()
            sites_up = result['sites_up'] if result else 0
            
            # Calculate sites down
            sites_down = total_sites - sites_up
            
            # Get average response time for successful pings
            cursor.execute("""
                SELECT AVG(ping_time_ms) AS avg_response_time
                FROM ping_logs
                WHERE timestamp >= %s AND ping_success = TRUE AND ping_time_ms IS NOT NULL
            """, (time_ago_str,))
            
            result = cursor.fetchone()
            avg_response_time = round(float(result['avg_response_time']), 2) if result and result['avg_response_time'] else 0
            
            # Get sites with loggers
            cursor.execute("""
                WITH recent_loggers AS (
                    SELECT 
                        pr_code,
                        length_loggers,
                        ROW_NUMBER() OVER (PARTITION BY pr_code ORDER BY timestamp DESC) AS rn
                    FROM ping_logs
                    WHERE timestamp >= %s AND length_loggers IS NOT NULL
                )
                SELECT COUNT(*) AS sites_with_loggers,
                AVG(length_loggers) AS avg_loggers_per_site
                FROM recent_loggers
                WHERE rn = 1 AND length_loggers > 0
            """, (time_ago_str,))
            
            result = cursor.fetchone()
            sites_with_loggers = result['sites_with_loggers'] if result else 0
            avg_loggers_per_site = round(float(result['avg_loggers_per_site']), 1) if result and result['avg_loggers_per_site'] else 0
            
            # Get uptime percentage for the last 24 hours
            cursor.execute("""
                SELECT 
                    pr_code,
                    AVG(CASE WHEN ping_success = TRUE THEN 1 ELSE 0 END) * 100 AS uptime_percentage
                FROM ping_logs
                WHERE timestamp >= %s
                GROUP BY pr_code
            """, (time_ago_str,))
            
            uptime_results = cursor.fetchall()
            avg_uptime = 0
            
            if uptime_results:
                uptime_sum = sum(float(result['uptime_percentage']) for result in uptime_results)
                avg_uptime = round(uptime_sum / len(uptime_results), 2)
                
            # Check timezone for Jakarta
            if datetime.now().astimezone().utcoffset() != timedelta(hours=7):
                logger.info("Timezone is not set to Jakarta (UTC+7).")
                timestamp = (datetime.now() + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M:%S')
            else:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Return the summary
            return {
                'total_sites': total_sites,
                'sites_up': sites_up,
                'sites_down': sites_down,
                'uptime_percentage': avg_uptime,
                'average_response_time': avg_response_time,
                'sites_with_loggers': sites_with_loggers,
                'average_loggers_per_site': avg_loggers_per_site,
                'time_period': f"Last {hours} hours",
                'timestamp': timestamp
            }
            
        except psycopg2.Error as e:
            logger.error(f"Error getting ping logs summary: {e}")
            return {}
        finally:
            if connection:
                connection.close()

    @staticmethod
    def get_down_sites(hours=24):
        """
        Get a list of sites that are currently down
        
        Args:
            hours (int): Number of hours to look back
            
        Returns:
            list: List of down sites with details
        """
        connection = None
        try:
            connection = Database.get_connection()
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            
            # Get the timestamp for X hours ago
            time_ago = datetime.now() - timedelta(hours=hours)
            time_ago_str = time_ago.strftime('%Y-%m-%d %H:%M:%S')
            
            # Find down sites based on most recent ping
            cursor.execute("""
                WITH recent_pings AS (
                    SELECT 
                        pr_code,
                        site_name,
                        ip_address,
                        ping_success,
                        timestamp,
                        ROW_NUMBER() OVER (PARTITION BY pr_code ORDER BY timestamp DESC) AS rn
                    FROM ping_logs
                    WHERE timestamp >= %s
                )
                SELECT 
                    pr_code,
                    site_name,
                    ip_address,
                    timestamp AS last_check
                FROM recent_pings
                WHERE rn = 1 AND ping_success = FALSE
                ORDER BY site_name
            """, (time_ago_str,))
            
            down_sites = cursor.fetchall()
            
            # Format the datetime for JSON
            for site in down_sites:
                if 'last_check' in site and site['last_check']:
                    if isinstance(site['last_check'], datetime):
                        site['last_check'] = site['last_check'].strftime('%Y-%m-%d %H:%M:%S')
            
            return down_sites
            
        except psycopg2.Error as e:
            logger.error(f"Error getting down sites: {e}")
            return []
        finally:
            if connection:
                connection.close()