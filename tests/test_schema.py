import pytest
from core.schema_models import DatabaseSchema, TableSchema, ColumnSchema, ForeignKeyConstraint
from core.gemma_client import GemmaClient
from agents.schema_agent import SchemaAgent
from validators.schema_validator import SchemaValidator

def test_topological_sort_order():
    """Verify parent tables come before dependent child tables."""
    parent_table = TableSchema(
        name="users",
        columns=[ColumnSchema(name="id", data_type="BIGINT", is_primary_key=True)],
        primary_keys=["id"]
    )
    child_table = TableSchema(
        name="orders",
        columns=[
            ColumnSchema(name="id", data_type="BIGINT", is_primary_key=True),
            ColumnSchema(name="user_id", data_type="BIGINT", is_foreign_key=True)
        ],
        primary_keys=["id"],
        foreign_keys=[
            ForeignKeyConstraint(column_name="user_id", target_table="users", target_column="id")
        ]
    )

    # Pass in child first, verify topological sort puts parent first
    db = DatabaseSchema(database_name="test_db", tables=[child_table, parent_table])
    ordered = db.get_topological_order()

    names = [t.name for t in ordered]
    assert names == ["users", "orders"], f"Expected ['users', 'orders'], got {names}"

def test_schema_agent_normalization():
    """Test SchemaAgent snake_casing and automatic PK creation."""
    client = GemmaClient(provider="mock")
    agent = SchemaAgent(client)

    raw_data = {
        "database_name": "MyStoreApp",
        "tables": [
            {
                "name": "CustomerAccounts",
                "columns": [
                    {"name": "EmailAddress", "data_type": "string"},
                    {"name": "TotalBalance", "data_type": "money"}
                ]
            }
        ]
    }

    schema = agent.normalize_schema(raw_data)
    assert schema.database_name == "my_store_app"
    table = schema.tables[0]
    assert table.name == "customer_accounts"
    # Verify auto-generated synthetic PK
    assert "id" in table.primary_keys
    # Verify money mapped to DECIMAL(10,2)
    bal_col = table.get_column("total_balance")
    assert bal_col is not None
    assert bal_col.data_type == "DECIMAL(10,2)"

def test_schema_validator_catches_invalid_fk():
    """Verify validator catches foreign keys referencing non-existent tables."""
    validator = SchemaValidator()
    invalid_schema = DatabaseSchema(
        database_name="bad_db",
        tables=[
            TableSchema(
                name="posts",
                columns=[
                    ColumnSchema(name="id", data_type="BIGINT", is_primary_key=True),
                    ColumnSchema(name="author_id", data_type="BIGINT", is_foreign_key=True)
                ],
                primary_keys=["id"],
                foreign_keys=[
                    ForeignKeyConstraint(column_name="author_id", target_table="ghost_users", target_column="id")
                ]
            )
        ]
    )

    res = validator.validate_schema(invalid_schema)
    assert not res.is_valid
    assert any("ghost_users" in issue.message for issue in res.issues)
