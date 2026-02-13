"""A simple script to view all threads and messages stored in SQLite, formatted with Rich."""

import argparse
import json
import sqlite3
import sys

from rich import print
from rich.console import Group
from rich.panel import Panel

DB_PATH = "chat_history.sqlite3"

parser = argparse.ArgumentParser(description="View threads and messages in the SQLite chat history database.")
parser.add_argument("--db", default=DB_PATH, help="Path to the SQLite database (default: chat_history.db)")
parser.add_argument("--values", action="store_true", help="Show messages for each thread (default: list threads only)")
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

# Get all threads with message counts
threads = conn.execute(
    "SELECT thread_id, COUNT(*) as count FROM messages GROUP BY thread_id ORDER BY thread_id"
).fetchall()

if not threads:
    print("[dim]No threads found in the database.[/dim]")
    sys.exit(0)

print(f"\n[bold]Found {len(threads)} thread(s) in {args.db}[/bold]\n")

if not args.values:
    for thread_id, count in threads:
        print(f"  [bold cyan]{thread_id}[/bold cyan] [dim]({count} messages)[/dim]")
    print()
    sys.exit(0)

for thread_id, count in threads:
    rows = conn.execute(
        "SELECT message_json FROM messages WHERE thread_id = ? ORDER BY id", (thread_id,)
    ).fetchall()

    panels = []
    for i, (message_json,) in enumerate(rows):
        try:
            parsed = json.loads(message_json)
            role = parsed.get("role", {}).get("value", "unknown")
            contents = parsed.get("contents", [])
            # Extract display text
            parts = []
            for c in contents:
                if c.get("type") == "text":
                    parts.append(c["text"])
                elif c.get("type") == "function_call":
                    parts.append(f"[tool call] {c['name']}({c['arguments']})")
                elif c.get("type") == "function_result":
                    parts.append(f"[tool result] {c['result']}")
            display = "\n".join(parts) if parts else json.dumps(parsed, indent=2)
            color = {"user": "blue", "assistant": "green", "tool": "yellow"}.get(role, "white")
            panels.append(
                Panel(display, title=f"[bold {color}]{role}[/bold {color}] [dim]({i + 1}/{count})[/dim]")
            )
        except json.JSONDecodeError:
            panels.append(Panel(message_json, title=f"[dim]item {i + 1}/{count}[/dim]"))

    print(
        Panel(
            Group(*panels),
            title=f"[bold cyan]{thread_id}[/bold cyan]",
            subtitle=f"[dim]{count} message(s)[/dim]",
        )
    )
    print()

conn.close()
