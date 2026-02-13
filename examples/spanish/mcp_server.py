"""
Servidor MCP de ejemplo para seguimiento de gastos.

Ejecuta este servidor primero y luego usa agent_mcp_local.py para conectarte:
    python examples/spanish/mcp_server.py
    python examples/spanish/agent_mcp_local.py
"""

import csv
import logging
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP

logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(message)s")
logger = logging.getLogger("ExpensesMCP")
logger.setLevel(logging.INFO)

SCRIPT_DIR = Path(__file__).parent
EXPENSES_FILE = SCRIPT_DIR / "expenses.csv"

mcp = FastMCP("Expenses Tracker")


class PaymentMethod(Enum):
    """Métodos de pago aceptados para gastos."""

    AMEX = "amex"
    VISA = "visa"
    CASH = "cash"


class Category(Enum):
    """Categorías de gastos para clasificación."""

    FOOD = "comida"
    TRANSPORT = "transporte"
    ENTERTAINMENT = "entretenimiento"
    SHOPPING = "compras"
    GADGET = "tecnologia"
    OTHER = "otro"


@mcp.tool
async def add_expense(
    expense_date: Annotated[date, "Expense date in YYYY-MM-DD format"],
    amount: Annotated[float, "Positive numeric expense amount"],
    category: Annotated[Category, "Category label"],
    description: Annotated[str, "Human-readable expense description"],
    payment_method: Annotated[PaymentMethod, "Payment method used"],
) -> str:
    """Agrega un nuevo gasto al archivo expenses.csv."""
    if amount <= 0:
        return "Error: El monto debe ser positivo"

    date_iso = expense_date.isoformat()
    logger.info(f"Agregando gasto: ${amount} por {description} el {date_iso}")

    try:
        file_exists = EXPENSES_FILE.exists()

        with open(EXPENSES_FILE, "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["date", "amount", "category", "description", "payment_method"])
            writer.writerow([date_iso, amount, category.value, description, payment_method.value])

        return f"Gasto agregado exitosamente: ${amount} por {description} el {date_iso}"

    except Exception as e:
        logger.error(f"Error al agregar gasto: {e!s}")
        return "Error: No se pudo agregar el gasto"


@mcp.resource("resource://expenses")
async def get_expenses_data() -> str:
    """Obtiene los datos de gastos desde el archivo CSV."""
    logger.info("Datos de gastos consultados")

    try:
        with open(EXPENSES_FILE, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            expenses_data = list(reader)

        csv_content = f"Datos de gastos ({len(expenses_data)} registros):\n\n"
        for expense in expenses_data:
            csv_content += (
                f"Fecha: {expense['date']}, "
                f"Monto: ${expense['amount']}, "
                f"Categoría: {expense['category']}, "
                f"Descripción: {expense['description']}, "
                f"Pago: {expense['payment_method']}\n"
            )
        return csv_content

    except FileNotFoundError:
        logger.error("Archivo de gastos no encontrado")
        return "Error: Datos de gastos no disponibles"
    except Exception as e:
        logger.error(f"Error al leer gastos: {e!s}")
        return "Error: No se pudieron obtener los datos de gastos"


if __name__ == "__main__":
    logger.info("Servidor MCP de Gastos iniciando (modo HTTP en puerto 8000)")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
