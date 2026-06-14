from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


SQLITE_ENTITY_TRANSACTION_COLUMNS = {
    "counterparty_account_name": "TEXT",
    "initiated_from_country": "VARCHAR(2)",
    "entity_registered_country": "VARCHAR(2)",
    "usual_operating_countries": "JSON",
}


def ensure_sqlite_schema(engine: Engine) -> None:
    """Apply tiny idempotent SQLite upgrades for hackathon demo databases."""

    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    if "entity_transactions" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("entity_transactions")}
    missing = [
        (name, column_type)
        for name, column_type in SQLITE_ENTITY_TRANSACTION_COLUMNS.items()
        if name not in existing
    ]
    if not missing:
        return

    with engine.begin() as connection:
        for name, column_type in missing:
            connection.execute(
                text(f"ALTER TABLE entity_transactions ADD COLUMN {name} {column_type}")
            )
