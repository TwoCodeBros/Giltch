
# db_connection.py (Modified for SQLite Fallback)

import logging
import os
import configparser
from dotenv import load_dotenv

load_dotenv()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DatabaseManager")

# --- AUTO-DETECTION ---
USE_SQLITE = False

try:
    import mysql.connector
    from mysql.connector import pooling, Error
    # Test connection? No, just assume success until retry fails
except ImportError:
    logger.warning("mysql.connector not found. Falling back to SQLite.")
    USE_SQLITE = True

class MySQLManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MySQLManager, cls).__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance

    def _initialize_pool(self, database=None):
        try:
            config = configparser.ConfigParser()
            config_path = os.path.join(os.path.dirname(__file__), 'db_config.ini')
            
            base_config = {
                "host": os.getenv('DB_HOST', 'localhost'),
                "port": int(os.getenv('DB_PORT', 3306)),
                "user": os.getenv('DB_USER', 'root'),
                "password": os.getenv('DB_PASSWORD', ''),
                "charset": "utf8mb4",
                "collation": "utf8mb4_unicode_ci"
            }
            
            # Ini overrides defaults, but ENV should override INI in a pure 12-factor app?
            # User Task: "Move the database root password... into a .env file... load them."
            # So Env > Ini.
            
            if os.path.exists(config_path):
                config.read(config_path)
                if 'mysql' in config:
                    read_config = dict(config['mysql'])
                    # Filter keys
                    for key in ['pool_name', 'pool_size', 'pool_reset_session']:
                        read_config.pop(key, None)
                    # Update base with INI? No, Env should win.
                    # Logic: Base (Env or Default) -> Update with INI (Legacy) -> Override with explicit Env if present?
                    # Let's assume INI is legacy/local. ENV is prod.
                    # If Env vars are set, they satisfy base_config.
                    # Let's just use Env vars if they exist, else INI.
                    # Simple way: Load INI first, then Env overrides.
                    base_config.update(read_config)

            # Override with Env if explicitly set (Reloading Env to be sure)
            if os.getenv('DB_HOST'): base_config['host'] = os.getenv('DB_HOST')
            if os.getenv('DB_USER'): base_config['user'] = os.getenv('DB_USER')
            if os.getenv('DB_PASSWORD') is not None: base_config['password'] = os.getenv('DB_PASSWORD')
            if os.getenv('DB_NAME'): base_config['database'] = os.getenv('DB_NAME')
            
            target_db = database or base_config.pop('database', 'debug_marathon_v3')


            try:
                full_config = base_config.copy()
                full_config['database'] = target_db
                self.pool = mysql.connector.pooling.MySQLConnectionPool(
                    pool_name="debug_marathon_pool",
                    pool_size=30,
                    pool_reset_session=True,
                    **full_config
                )
                logger.info(f"Connection pool initialized with database '{target_db}'.")
            except Error as e:
                if e.errno == 1049: # Unknown database
                    logger.warning(f"Database '{target_db}' not found. Connecting to server only.")
                    base_config.pop('database', None)
                    self.pool = mysql.connector.pooling.MySQLConnectionPool(
                        pool_name="debug_marathon_pool",
                        pool_size=30,
                        pool_reset_session=True,
                        **base_config
                    )
                else:
                    raise
        except Error as e:
            logger.error(f"Error initializing connection pool: {e}")
            raise

    def get_connection(self):
        try:
            conn = self.pool.get_connection()
            if conn.is_connected():
                return conn
            else:
                try:
                    conn.reconnect(attempts=3, delay=2)
                    return conn
                except:
                    return None
        except Error as e:
            logger.error(f"Failed to get connection from pool: {e}")
            return None

    def execute_query(self, query, params=None):
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
                try: cursor.close()
                except: pass
            if conn:
                try: conn.close()
                except: pass

    def execute_update(self, query, params=None):
        conn = self.get_connection()
        if not conn: return False
        
        cursor = conn.cursor()
        try:
            cursor.execute(query, params or ())
            conn.commit()
            return {"last_id": cursor.lastrowid, "affected": cursor.rowcount}
        except Error as e:
            conn.rollback()
            logger.error(f"UPDATE Query failed: {e}\nQuery: {query}")
            return False
        finally:
            if cursor:
                try: cursor.close()
                except: pass
            if conn:
                try: conn.close()
                except: pass

    def init_database(self, schema_file):
        if not os.path.exists(schema_file):
            logger.error(f"Schema file not found: {schema_file}")
            return False
        
        conn = self.get_connection()
        if not conn: return False
        
        cursor = conn.cursor()
        try:
            with open(schema_file, 'r') as f:
                sql = f.read()
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
            if cursor: cursor.close()
            if conn: conn.close()
            
    def upsert(self, table, data, conflict_keys):
        # Default MySQL implementation using ON DUPLICATE KEY UPDATE (manual Construction)
        # This is a fallback helper
        keys = list(data.keys())
        columns = ', '.join(keys)
        placeholders = ', '.join(['%s'] * len(keys))
        
        update_clause = ', '.join([f"{k}=VALUES({k})" for k in keys if k not in conflict_keys])
        
        if not update_clause:
            # Just INSERT IGNORE
            sql = f"INSERT IGNORE INTO {table} ({columns}) VALUES ({placeholders})"
        else:
            sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_clause}"
        
        vals = tuple(data.values())
        return self.execute_update(sql, vals)

# --- FACTORY ---

try:
    # Try initializing MySQL Manager
    if not USE_SQLITE:
        _temp = MySQLManager()
    db_manager = _temp
except Exception as e:
    logger.warning(f"MySQL Connection Failed ({e}). Switching to SQLite.")
    from db_sqlite import sqlite_manager
    db_manager = sqlite_manager
