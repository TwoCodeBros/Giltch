
import sqlite3
import logging
import os
import re

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SQLiteManager")

class SQLiteManager:
    _instance = None
    DB_FILE = 'debug_marathon.db'

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SQLiteManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the SQLite DB"""
        self.db_path = os.path.join(os.path.dirname(__file__), self.DB_FILE)
        logger.info(f"SQLite Manager initialized. DB Path: {self.db_path}")

    def get_connection(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Access columns by name
            return conn
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            return None

    def _adapt_query(self, query):
        """
        Adapt MySQL query to SQLite.
        1. Replace %s with ?
        2. Handle ON DUPLICATE KEY UPDATE -> This usually requires manual refactoring, 
           but for simple cases we might try to detect it or leave it to 'upsert' method.
           Here we ONLY handle placeholders.
        """
        # Replace %s with ?
        return query.replace('%s', '?')

    def execute_query(self, query, params=None):
        conn = self.get_connection()
        if not conn: return None
        
        cursor = conn.cursor()
        try:
            adapted_query = self._adapt_query(query)
            cursor.execute(adapted_query, params or ())
            result = [dict(row) for row in cursor.fetchall()]
            return result
        except sqlite3.Error as e:
            logger.error(f"SELECT Query failed (SQLite): {e}\nQuery: {query}")
            return None
        finally:
            if conn: conn.close()

    def execute_update(self, query, params=None, is_script=False):
        conn = self.get_connection()
        if not conn: return False
        
        cursor = conn.cursor()
        try:
            if 'ON DUPLICATE KEY UPDATE' in query:
                # We cannot automatically convert this reliably.
                # Caller should have used .upsert() or provided compatible SQL.
                # However, for 'setup_db' we might just let it fail if not handled?
                # Actually, our code uses it heavily.
                # We will attempt a crude regex fix if possible, OR log critical warning.
                 logger.warning("ON DUPLICATE KEY UPDATE detected in SQLite adapter. This may fail unless query is manually adapted.")
            
            adapted_query = self._adapt_query(query)
            
            if is_script:
                cursor.executescript(adapted_query)
                affected = -1
            else:
                cursor.execute(adapted_query, params or ())
                affected = cursor.rowcount
                
            conn.commit()
            last_id = cursor.lastrowid
            return {"last_id": last_id, "affected": affected}
        except sqlite3.Error as e:
            # logger.error(f"UPDATE Query failed (SQLite): {e}\nQuery: {query}")
            # Raise so we can catch it
            raise e
        finally:
            if conn: conn.close()

    def execute_transaction(self, queries_list):
        conn = self.get_connection()
        if not conn: return False
        
        cursor = conn.cursor()
        try:
            for query, params in queries_list:
                cursor.execute(self._adapt_query(query), params or ())
            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Transaction failed: {e}")
            return False
        finally:
            if conn: conn.close()

    def init_database(self, schema_file):
        # Override to use sqlite_schema.sql if provided, or caller handles it
        if not os.path.exists(schema_file):
            logger.error(f"Schema file not found: {schema_file}")
            return False
            
        try:
            with open(schema_file, 'r') as f:
                sql = f.read()
            self.execute_update(sql, is_script=True)
            logger.info("Database initialized successfully (SQLite).")
            return True
        except Exception as e:
            logger.error(f"init_db failed: {e}")
            return False

    # === Helper for Compatibility ===
    def upsert(self, table, data, conflict_keys):
        """
        Perform an INSERT OR REPLACE / ON CONFLICT UPDATE for SQLite.
        :param table: Table name
        :param data: Dictionary of col:val
        :param conflict_keys: List of columns that form the unique key
        """
        keys = list(data.keys())
        placeholders = ', '.join(['?'] * len(keys))
        columns = ', '.join(keys)
        
        # SQLite 3.24+ supports ON CONFLICT (col) DO UPDATE SET ...
        # Standard INSERT OR REPLACE is easier but replaces the row (new ID).
        # We generally want UPDATE semantics to preserve ID if not in data.
        
        # Construct update clause
        update_set = ', '.join([f"{k}=excluded.{k}" for k in keys if k not in conflict_keys])
        
        conflict_target = ', '.join(conflict_keys)
        
        if not update_set:
            # Nothing to update (only keys provided), use IGNORE
            sql = f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})"
        else:
            sql = f"""
                INSERT INTO {table} ({columns}) VALUES ({placeholders})
                ON CONFLICT({conflict_target}) DO UPDATE SET {update_set}
            """
        
        vals = tuple(data.values())
        return self.execute_update(sql, vals)

sqlite_manager = SQLiteManager()
