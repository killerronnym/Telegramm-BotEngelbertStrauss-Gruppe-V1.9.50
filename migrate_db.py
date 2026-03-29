import os
import sys
from web_dashboard.app import create_app, db
from sqlalchemy import text

app = create_app()

def migrate():
    with app.app_context():
        print("Checking for missing columns in id_finder_user...")
        columns = db.session.execute(text("PRAGMA table_info(id_finder_user)")).fetchall()
        column_names = [c[1] for c in columns]
        print(f"Existing columns: {column_names}")
        
        needed = [
            ("photo_file_id", "VARCHAR(200)"),
            ("photo_url", "VARCHAR(500)"),
            ("photo_cached_at", "DATETIME")
        ]
        
        for name, dtype in needed:
            if name not in column_names:
                print(f"Adding column {name}...")
                try:
                    db.session.execute(text(f"ALTER TABLE id_finder_user ADD COLUMN {name} {dtype}"))
                    db.session.commit()
                    print(f"Column {name} added.")
                except Exception as e:
                    db.session.rollback()
                    print(f"Error adding {name}: {e}")
            else:
                print(f"Column {name} already exists.")

if __name__ == "__main__":
    migrate()
