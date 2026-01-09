"""
Migration: Add maintenance_tasks table
======================================
This migration creates the maintenance_tasks table for recurring equipment maintenance.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from database.session import init_db

def migrate():
    """Add maintenance_tasks table."""
    db = init_db()
    engine = db.engine
    
    # Check if table already exists
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_tasks'"
        ))
        if result.fetchone():
            print("Table 'maintenance_tasks' already exists, skipping...")
            return
    
    # Create the table
    with engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE maintenance_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL REFERENCES equipment(id),
                name VARCHAR(255) NOT NULL,
                description TEXT,
                interval_days INTEGER NOT NULL,
                issue_title VARCHAR(255) NOT NULL,
                issue_description TEXT,
                issue_category VARCHAR(50) DEFAULT 'maintenance',
                issue_priority VARCHAR(50) DEFAULT 'medium',
                default_assignee_id INTEGER REFERENCES users(id),
                is_active BOOLEAN DEFAULT 1,
                last_triggered_at DATETIME,
                next_due_date DATE,
                current_issue_id INTEGER REFERENCES equipment_issues(id),
                created_by_id INTEGER REFERENCES users(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                trashed_at DATETIME,
                trashed_by VARCHAR(100)
            )
        '''))
        
        # Create indexes
        conn.execute(text('CREATE INDEX idx_maintenance_tasks_equipment ON maintenance_tasks(equipment_id)'))
        conn.execute(text('CREATE INDEX idx_maintenance_tasks_active ON maintenance_tasks(is_active)'))
        conn.execute(text('CREATE INDEX idx_maintenance_tasks_next_due ON maintenance_tasks(next_due_date)'))
        
        conn.commit()
    
    print("Successfully created 'maintenance_tasks' table")

if __name__ == '__main__':
    migrate()
