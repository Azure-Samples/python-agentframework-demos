"""Un script simple para ver todas las sesiones y mensajes guardados en SQLite, con formato usando Rich."""

import argparse
import json
import sqlite3
import sys

from rich import print
from rich.panel import Panel
from rich.syntax import Syntax

DB_PATH = "chat_history.sqlite3"

parser = argparse.ArgumentParser(
    description="Ver sesiones y mensajes en la base de datos SQLite del historial de chat."
)
parser.add_argument(
    "--db",
    default=DB_PATH,
    help="Ruta a la base de datos SQLite (por defecto: chat_history.sqlite3)",
)
parser.add_argument(
    "--values",
    action="store_true",
    help="Mostrar mensajes de cada sesión (por defecto: solo listar sesiones)",
)
args = parser.parse_args()

try:
    conn = sqlite3.connect(args.db)
    # Verificar que la tabla exista
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
    if not cursor.fetchone():
        print(f"[red]No se encontró la tabla 'messages' en {args.db}[/red]")
        sys.exit(1)
except sqlite3.Error as e:
    print(f"[red]No se puede abrir la base de datos {args.db}: {e}[/red]")
    sys.exit(1)

# Obtener todas las sesiones con conteo de mensajes
sessions = conn.execute(
    "SELECT session_id, COUNT(*) as count FROM messages GROUP BY session_id ORDER BY session_id"
).fetchall()

if not sessions:
    print("[dim]No se encontraron sesiones en la base de datos.[/dim]")
    sys.exit(0)

print(f"\n[bold]Se encontraron {len(sessions)} sesión(es) en {args.db}[/bold]\n")

if not args.values:
    for session_id, count in sessions:
        print(f"  [bold cyan]{session_id}[/bold cyan] [dim]({count} mensajes)[/dim]")
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
            subtitle=f"[dim]{count} elemento(s)[/dim]",
        )
    )
    print()

conn.close()
