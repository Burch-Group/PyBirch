"""Migration script to create computers table and migrate existing binding data."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.session import get_db

def migrate():
    db = get_db()
    engine = db.engine
    conn = engine.connect()

    # Create computers table
    conn.execute(text('''
    CREATE TABLE IF NOT EXISTS computers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        computer_name VARCHAR(255) NOT NULL UNIQUE,
        computer_id VARCHAR(255),
        nickname VARCHAR(255),
        description TEXT,
        location VARCHAR(255),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    '''))
    print('Created computers table')

    # Add computer_id_fk column to computer_bindings if not exists
    try:
        conn.execute(text('ALTER TABLE computer_bindings ADD COLUMN computer_id_fk INTEGER REFERENCES computers(id)'))
        print('Added computer_id_fk column')
    except Exception as e:
        print(f'computer_id_fk column may already exist: {e}')

    # Create indexes
    try:
        conn.execute(text('CREATE INDEX IF NOT EXISTS idx_computer_name ON computers(computer_name)'))
        conn.execute(text('CREATE INDEX IF NOT EXISTS idx_computer_nickname ON computers(nickname)'))
        print('Created indexes')
    except Exception as e:
        print(f'Index creation: {e}')

    conn.commit()
    print('Database schema updated successfully')

    # Migrate existing bindings to create Computer records
    result = conn.execute(text('SELECT DISTINCT computer_name, computer_id FROM computer_bindings'))
    bindings = result.fetchall()
    print(f'Found {len(bindings)} unique computers in bindings')

    from datetime import datetime
    now = datetime.utcnow().isoformat()
    
    for computer_name, computer_id in bindings:
        # Check if computer already exists
        existing = conn.execute(text('SELECT id FROM computers WHERE computer_name = :name'), {'name': computer_name}).fetchone()
        if not existing:
            conn.execute(text('INSERT INTO computers (computer_name, computer_id, created_at, updated_at) VALUES (:name, :cid, :now, :now)'), 
                        {'name': computer_name, 'cid': computer_id, 'now': now})
            print(f'Created Computer record for {computer_name}')
        
        # Update binding to link to computer
        computer_row = conn.execute(text('SELECT id FROM computers WHERE computer_name = :name'), {'name': computer_name}).fetchone()
        if computer_row:
            conn.execute(text('UPDATE computer_bindings SET computer_id_fk = :cid WHERE computer_name = :name'),
                        {'cid': computer_row[0], 'name': computer_name})

    conn.commit()
    print('Migration complete')

if __name__ == '__main__':
    migrate()
