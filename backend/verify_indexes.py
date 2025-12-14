import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Get all indexes for our tables
tables = [
    'audioDiagnostic_audioproject',
    'audioDiagnostic_audiofile',
    'audioDiagnostic_transcriptionsegment',
    'audioDiagnostic_transcriptionword'
]

print("Database Indexes Verification")
print("=" * 80)

for table in tables:
    print(f"\n{table}:")
    indexes = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
        (table,)
    ).fetchall()
    
    if indexes:
        for idx in indexes:
            print(f"  ✓ {idx[0]}")
    else:
        print("  (no custom indexes)")

conn.close()
