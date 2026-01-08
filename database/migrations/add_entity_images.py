"""
Migration script to add entity_images table for storing images attached to entities.
Run this once to update existing databases for image support.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.session import init_db

def migrate():
    """Create the entity_images table."""
    db = init_db()
    
    with db.session() as session:
        # Check if table exists
        try:
            session.execute(text("SELECT id FROM entity_images LIMIT 1"))
            print("✓ entity_images table already exists")
            return
        except Exception:
            pass
        
        # Create the entity_images table
        try:
            session.execute(text("""
                CREATE TABLE entity_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type VARCHAR(50) NOT NULL,
                    entity_id INTEGER NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    stored_filename VARCHAR(255) NOT NULL,
                    name VARCHAR(255),
                    description TEXT,
                    file_size_bytes INTEGER,
                    mime_type VARCHAR(100),
                    width INTEGER,
                    height INTEGER,
                    uploaded_by VARCHAR(100),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            session.commit()
            print("✓ Created entity_images table")
            
            # Create indexes
            session.execute(text("""
                CREATE INDEX idx_entity_images ON entity_images (entity_type, entity_id)
            """))
            session.execute(text("""
                CREATE INDEX idx_entity_images_created ON entity_images (created_at)
            """))
            session.commit()
            print("✓ Created indexes for entity_images table")
            
        except Exception as e:
            print(f"Error creating entity_images table: {e}")
            session.rollback()
            raise


if __name__ == "__main__":
    print("Running entity_images migration...")
    migrate()
    print("Migration complete!")
