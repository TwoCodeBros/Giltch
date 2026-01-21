# db_connection.py
# Production-ready Python Database Manager for Debug Marathon
# Features: Connection Pooling, Auto-reconnect, Transaction Support

import mysql.connector
from mysql.connector import pooling, Error
import logging
import os
import configparser

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("db_operations.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DatabaseManager")

class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance

    def _initialize_pool(self, database=None):
        """Initialize the MySQL Connection Pool"""
        try:
            config = configparser.ConfigParser()
            config_path = os.path.join(os.path.dirname(__file__), 'db_config.ini')
            
            # Base config without database
            base_config = {
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "",
                "charset": "utf8mb4",
                "collation": "utf8mb4_unicode_ci"
            }
            
            if os.path.exists(config_path):
                config.read(config_path)
                if 'mysql' in config:
                    read_config = dict(config['mysql'])
                    # Remove pool-related keys to avoid conflict
                    for key in ['pool_name', 'pool_size', 'pool_reset_session']:
                        read_config.pop(key, None)
                    base_config.update(read_config)

            # Target database
            target_db = database or base_config.pop('database', 'debug_marathon')

            # Try to connect with the target database
            try:
                full_config = base_config.copy()
                full_config['database'] = target_db
                self.pool = mysql.connector.pooling.MySQLConnectionPool(
                    pool_name="debug_marathon_pool",
                    pool_size=5,
                    pool_reset_session=True,
                    **full_config
                )
                logger.info(f"Connection pool initialized with database '{target_db}'.")
            except Error as e:
                if e.errno == 1049: # Unknown database
                    logger.warning(f"Database '{target_db}' not found. Connecting to server only.")
                    # Ensure database is not in base_config for server-only connection
                    base_config.pop('database', None)
                    self.pool = mysql.connector.pooling.MySQLConnectionPool(
                        pool_name="debug_marathon_pool",
                        pool_size=5,
                        pool_reset_session=True,
                        **base_config
                    )
                else:
                    raise
        except Error as e:
            logger.error(f"Error initializing connection pool: {e}")
            raise



    def get_connection(self):
        """Get a connection from the pool"""
        try:
            conn = self.pool.get_connection()
            if conn.is_connected():
                return conn
            else:
                # Attempt to reconnect
                logger.warning("Connection lost, attempting to reconnect...")
                conn.reconnect(attempts=3, delay=2)
                return conn
        except Error as e:
            logger.error(f"Failed to get connection from pool: {e}")
            return None

    def execute_query(self, query, params=None):
        """Execute SELECT queries and return results"""
        conn = self.get_connection()
        if not conn: return None
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, params or ())
            result = cursor.fetchall()
            return result
        except Error as e:
            logger.error(f"SELECT Query failed: {e}\nQuery: {query}")
            return None
        finally:
            if cursor:
                try:
                    cursor.close()
                except: pass
            if conn:
                try:
                    conn.close()
                except Error as err:
                    logger.warning(f"Error closing connection: {err}")

    def execute_update(self, query, params=None):
        """Execute INSERT/UPDATE/DELETE queries"""
        conn = self.get_connection()
        if not conn: return False
        
        cursor = conn.cursor()
        try:
            cursor.execute(query, params or ())
            conn.commit()
            last_id = cursor.lastrowid
            affected = cursor.rowcount
            logger.info(f"Update executed: {affected} rows affected.")
            return {"last_id": last_id, "affected": affected}
        except Error as e:
            conn.rollback()
            logger.error(f"UPDATE Query failed: {e}\nQuery: {query}")
            return False
        finally:
            if cursor:
                try:
                    cursor.close()
                except: pass
            if conn:
                try:
                    conn.close()
                except Error as err:
                    logger.warning(f"Error closing connection: {err}")

    def execute_transaction(self, queries_list):
        """Execute multiple queries in a single atomic transaction"""
        conn = self.get_connection()
        if not conn: return False
        
        cursor = conn.cursor()
        try:
            for query, params in queries_list:
                cursor.execute(query, params or ())
            conn.commit()
            logger.info("Transaction completed successfully.")
            return True
        except Error as e:
            conn.rollback()
            logger.error(f"Transaction failed: {e}")
            return False
        finally:
            if cursor:
                try:
                    cursor.close()
                except: pass
            if conn:
                try:
                    conn.close()
                except Error as err:
                    logger.warning(f"Error closing connection: {err}")

    def init_database(self, schema_file):
        """Create all tables from a schema file if they don't exist"""
        if not os.path.exists(schema_file):
            logger.error(f"Schema file not found: {schema_file}")
            return False
        
        conn = self.get_connection()
        if not conn: return False
        
        cursor = conn.cursor()
        try:
            with open(schema_file, 'r') as f:
                sql = f.read()
            
            # Split by semicolon to execute one by one
            statements = sql.split(';')
            for statement in statements:
                if statement.strip():
                    cursor.execute(statement)
            conn.commit()
            logger.info("Database initialized successfully.")
            return True
        except Error as e:
            logger.error(f"Failed to initialize database: {e}")
            return False
        finally:
            if cursor:
                try:
                    cursor.close()
                except: pass
            if conn:
                try:
                    conn.close()
                except Error as err:
                    logger.warning(f"Error closing connection: {err}")

# Export a default instance
db_manager = DatabaseManager()
