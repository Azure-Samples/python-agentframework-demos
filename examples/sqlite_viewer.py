"""A simple script to view all sessions and messages stored in SQLite, formatted with Rich."""

import argparse
import json
import sqlite3
import sys

from rich import print
from rich.panel import Panel
from rich.syntax import Syntax

DB_PATH = "chat_history.sqlite3"

parser = argparse.ArgumentParser(description="View sessions and messages in the SQLite chat history database.")
parser.add_argument("--db", default=DB_PATH, help="Path to the SQLite database (default: chat_history.sqlite3)")
parser.add_argument(
    "--values", action="store_true", help="Show messages for each session (default: list sessions only)"
)
args = parser.parse_args()

try:
    conn = sqlite3.connect(args.db)
    # Verify the table exists
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
    if not cursor.fetchone():
        print(f"[red]No 'messages' table found in {args.db}[/red]")
        sys.exit(1)
except sqlite3.Error as e:
    print(f"[red]Cannot open database {args.db}: {e}[/red]")
    sys.exit(1)

# Get all sessions with message counts
sessions = conn.execute(
    "SELECT session_id, COUNT(*) as count FROM messages GROUP BY session_id ORDER BY session_id"
).fetchall()

if not sessions:
    print("[dim]No sessions found in the database.[/dim]")
    sys.exit(0)

print(f"\n[bold]Found {len(sessions)} session(s) in {args.db}[/bold]\n")

if not args.values:
    for session_id, count in sessions:
        print(f"  [bold cyan]{session_id}[/bold cyan] [dim]({count} messages)[/dim]")
    print()
    sys.exit(0)

for session_id, count in sessions:
    rows = conn.execute("SELECT message_json FROM messages WHERE session_id = ? ORDER BY id", (session_id,)).fetchall()

    parts = []
    for (message_json,) in rows:
        try:
            formatted = json.dumps(json.loads(message_json), indent=2)
        except json.JSONDecodeError:
            formatted = message_json
        parts.append(formatted)
    combined = "\n---\n".join(parts)
    content = Syntax(combined, "json", theme="monokai", word_wrap=True)
    print(
        Panel(
            content,
            title=f"[bold cyan]{session_id}[/bold cyan]",
            subtitle=f"[dim]{count} item(s)[/dim]",
        )
    )
    print()

conn.close()
