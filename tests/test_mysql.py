import pytest
from core.schema_models import DatabaseSchema, TableSchema, ColumnSchema, ForeignKeyConstraint
from generators.mysql_generator import MySQLGenerator
from validators.sql_validator import SQLValidator

def test_mysql_ddl_generation_and_validation():
    """Verify MySQLGenerator produces syntactically correct SQL."""
    generator = MySQLGenerator()
    sql_validator = SQLValidator()

    users_tbl = TableSchema(
        name="users",
        columns=[
            ColumnSchema(name="id", data_type="BIGINT", is_primary_key=True, auto_increment=True),
            ColumnSchema(name="username", data_type="VARCHAR(50)", is_unique=True, is_nullable=False),
            ColumnSchema(name="email", data_type="VARCHAR(120)", is_unique=True, is_nullable=False)
        ],
        primary_keys=["id"]
    )

    orders_tbl = TableSchema(
        name="orders",
        columns=[
            ColumnSchema(name="id", data_type="BIGINT", is_primary_key=True, auto_increment=True),
            ColumnSchema(name="user_id", data_type="BIGINT", is_foreign_key=True, is_nullable=False),
            ColumnSchema(name="total_amount", data_type="DECIMAL(10,2)", is_nullable=False)
        ],
        primary_keys=["id"],
        foreign_keys=[
            ForeignKeyConstraint(column_name="user_id", target_table="users", target_column="id")
        ]
    )

    schema = DatabaseSchema(
        database_name="shop_db",
        tables=[orders_tbl, users_tbl]
    )

    sql = generator.generate_sql(schema)

    # Basic assertions
    assert "CREATE DATABASE IF NOT EXISTS `shop_db`" in sql
    assert "CREATE TABLE `users`" in sql
    assert "CREATE TABLE `orders`" in sql
    assert "CONSTRAINT `fk_orders_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)" in sql
    assert "ENGINE=InnoDB" in sql

    # Pass through SQLValidator
    val_res = sql_validator.validate_sql(sql)
    assert val_res["is_valid"], f"SQL Validator failed with errors: {val_res['errors']}"
