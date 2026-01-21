import os
import json
import time
import logging
from db_connection import db_manager
from config import Config

# Fallback Mock for safety, though we now prefer MySQL
class MySQLBridge:
    """Bridges the existing Supabase-style calls to our new MySQL Manager"""
    def table(self, table_name):
        return MySQLTable(table_name)
    
    def execute_query(self, query, params=None):
        return db_manager.execute_query(query, params)

    def execute_update(self, query, params=None):
        return db_manager.execute_update(query, params)

class MySQLTable:
    def __init__(self, table_name):
        self.table_name = table_name
        self.filters = {}
        self.update_data = {}

    def select(self, *args):
        return self

    def insert(self, data):
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        values = tuple(data.values())
        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        db_manager.execute_update(query, values)
        return self

    def update(self, data):
        self.update_data = data
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def delete(self):
        self.is_delete = True
        return self

    def execute(self):
        pk_col = f"{self.table_name.rstrip('s')}_id"
        is_delete = getattr(self, 'is_delete', False)
        
        # Translate 'id' in filters to native PK column
        mapped_filters = {}
        for k, v in self.filters.items():
            if k == 'id':
                mapped_filters[pk_col] = v
            else:
                mapped_filters[k] = v

        if is_delete:
            where_clause = " AND ".join([f"{k} = %s" for k in mapped_filters.keys()])
            values = tuple(mapped_filters.values())
            query = f"DELETE FROM {self.table_name} WHERE {where_clause}"
            db_manager.execute_update(query, values)
            self.is_delete = False
            return type('obj', (object,), {'success': True})
        elif self.update_data:
            # Handle UPDATE
            set_clause = ", ".join([f"{k} = %s" for k in self.update_data.keys()])
            where_clause = " AND ".join([f"{k} = %s" for k in mapped_filters.keys()])
            values = tuple(list(self.update_data.values()) + list(mapped_filters.values()))
            query = f"UPDATE {self.table_name} SET {set_clause} WHERE {where_clause}"
            db_manager.execute_update(query, values)
            self.update_data = {} # Reset
            return type('obj', (object,), {'success': True})
        else:
            # Handle SELECT
            where_clause = ""
            values = ()
            if mapped_filters:
                where_clause = " WHERE " + " AND ".join([f"{k} = %s" for k in mapped_filters.keys()])
                values = tuple(mapped_filters.values())
            
            query = f"SELECT * FROM {self.table_name}{where_clause}"
            res = db_manager.execute_query(query, values)
            
            # Map primary keys like contest_id to 'id' for frontend compatibility
            transformed = []
            if res:
                for item in res:
                    new_item = item.copy()
                    if pk_col in item and 'id' not in item:
                        new_item['id'] = item[pk_col]
                    
                    # Special mapping for users table to match frontend expectations
                    if self.table_name == 'users':
                        if 'username' in item: new_item['participant_id'] = item['username']
                        if 'full_name' in item: new_item['name'] = item['full_name']
                        
                    transformed.append(new_item)
            return type('obj', (object,), {'data': transformed})


def get_db():
    # We now return a bridge to our MySQL DatabaseManager
    return MySQLBridge()

