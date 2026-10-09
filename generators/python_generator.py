import re
from typing import List
from core.schema_models import DatabaseSchema, TableSchema, ColumnSchema

class PythonGenerator:
    """
    Python Generator:
    Generates SQLAlchemy 2.0 ORM models, Pydantic v2 schemas,
    and FastAPI route skeletons from the relational schema.
    """

    SQL_TO_PY_TYPE = {
        "BIGINT": "int",
        "INT": "int",
        "SMALLINT": "int",
        "TINYINT": "int",
        "BOOLEAN": "bool",
        "VARCHAR": "str",
        "CHAR": "str",
        "TEXT": "str",
        "LONGTEXT": "str",
        "DECIMAL": "Decimal",
        "FLOAT": "float",
        "DOUBLE": "float",
        "DATE": "date",
        "DATETIME": "datetime",
        "TIMESTAMP": "datetime",
        "JSON": "dict"
    }

    def generate_sqlalchemy_models(self, schema: DatabaseSchema) -> str:
        """
        Generates modern SQLAlchemy 2.0 Declarative Base models.
        """
        lines: List[str] = [
            "# Auto-generated SQLAlchemy 2.0 Models by SchemaMindAI",
            "from __future__ import annotations",
            "from datetime import datetime, date",
            "from decimal import Decimal",
            "from typing import Optional, List",
            "from sqlalchemy import String, Integer, BigInteger, Boolean, Numeric, DateTime, Date, Text, ForeignKey",
            "from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship",
            "",
            "class Base(DeclarativeBase):",
            "    pass",
            ""
        ]

        for table in schema.tables:
            cls_name = self._to_pascal(table.name)
            lines.append(f"class {cls_name}(Base):")
            lines.append(f'    __tablename__ = "{table.name}"')
            lines.append("")

            for col in table.columns:
                py_type = self._map_sql_to_python(col.data_type)
                opt_wrap = f"Optional[{py_type}]" if col.is_nullable and not col.is_primary_key else py_type

                # Map SQLAlchemy Column type
                sa_type = self._map_sql_to_sa(col.data_type)
                args = [sa_type]

                if col.is_primary_key:
                    args.append("primary_key=True")
                    if col.auto_increment:
                        args.append("autoincrement=True")

                if col.foreign_key_target:
                    args.append(f'ForeignKey("{col.foreign_key_target}")')

                if not col.is_nullable and not col.is_primary_key:
                    args.append("nullable=False")

                if col.is_unique and not col.is_primary_key:
                    args.append("unique=True")

                col_args_str = ", ".join(args)
                lines.append(f"    {col.name}: Mapped[{opt_wrap}] = mapped_column({col_args_str})")

            # Relationships
            for fk in table.foreign_keys:
                parent_cls = self._to_pascal(fk.target_table)
                prop_name = fk.target_table.rstrip("s").lower()
                lines.append(f'    {prop_name}: Mapped["{parent_cls}"] = relationship(back_populates="{table.name}")')

            lines.append("")

        return "\n".join(lines)

    def generate_pydantic_schemas(self, schema: DatabaseSchema) -> str:
        """
        Generates Pydantic v2 validation models.
        """
        lines: List[str] = [
            "# Auto-generated Pydantic v2 Schemas by SchemaMindAI",
            "from datetime import datetime, date",
            "from decimal import Decimal",
            "from typing import Optional, List",
            "from pydantic import BaseModel, ConfigDict",
            ""
        ]

        for table in schema.tables:
            base_cls = self._to_pascal(table.name)
            non_pk_cols = [c for c in table.columns if not c.is_primary_key]

            # 1. Base Schema
            lines.append(f"class {base_cls}Base(BaseModel):")
            for col in non_pk_cols:
                py_type = self._map_sql_to_python(col.data_type)
                if col.is_nullable:
                    lines.append(f"    {col.name}: Optional[{py_type}] = None")
                else:
                    lines.append(f"    {col.name}: {py_type}")
            lines.append("")

            # 2. Create Schema
            lines.append(f"class {base_cls}Create({base_cls}Base):")
            lines.append("    pass")
            lines.append("")

            # 3. Response Schema
            lines.append(f"class {base_cls}Response({base_cls}Base):")
            lines.append("    model_config = ConfigDict(from_attributes=True)")
            for pk in table.get_pk_columns():
                pk_type = self._map_sql_to_python(pk.data_type)
                lines.append(f"    {pk.name}: {pk_type}")
            lines.append("")

        return "\n".join(lines)

    def generate_fastapi_endpoints(self, schema: DatabaseSchema) -> str:
        """
        Generates FastAPI CRUD router endpoints.
        """
        lines: List[str] = [
            "# Auto-generated FastAPI CRUD Endpoints by SchemaMindAI",
            "from fastapi import APIRouter, HTTPException, Depends, status",
            "from typing import List",
            "",
            "router = APIRouter(prefix=\"/api/v1\", tags=[\"Generated APIs\"])",
            ""
        ]

        for table in schema.tables:
            cls_name = self._to_pascal(table.name)
            t_name = table.name.lower()
            lines.extend([
                f"@router.get('/{t_name}', response_model=List[dict])",
                f"async def list_{t_name}():",
                f"    '''Fetch all records from {t_name}'''",
                f"    return []",
                "",
                f"@router.post('/{t_name}', status_code=status.HTTP_201_CREATED)",
                f"async def create_{t_name}(payload: dict):",
                f"    '''Create a new record in {t_name}'''",
                f"    return {{'message': '{cls_name} created successfully', 'data': payload}}",
                "",
                f"@router.get('/{t_name}/{{item_id}}')",
                f"async def get_{t_name}(item_id: int):",
                f"    '''Fetch a single record by primary key'''",
                f"    return {{'id': item_id, 'table': '{t_name}'}}",
                ""
            ])

        return "\n".join(lines)

    def _map_sql_to_python(self, sql_type: str) -> str:
        base = sql_type.split("(")[0].strip().upper()
        return self.SQL_TO_PY_TYPE.get(base, "str")

    def _map_sql_to_sa(self, sql_type: str) -> str:
        base = sql_type.split("(")[0].strip().upper()
        if "BIGINT" in base:
            return "BigInteger"
        if "INT" in base:
            return "Integer"
        if "VARCHAR" in base or "CHAR" in base:
            match = re.search(r"\((\d+)\)", sql_type)
            length = match.group(1) if match else "255"
            return f"String({length})"
        if "TEXT" in base:
            return "Text"
        if "DECIMAL" in base:
            return "Numeric(10, 2)"
        if "BOOLEAN" in base:
            return "Boolean"
        if "DATETIME" in base:
            return "DateTime"
        if "TIMESTAMP" in base:
            return "DateTime"
        if "DATE" in base:
            return "Date"
        return "String(255)"

    @staticmethod
    def _to_pascal(name: str) -> str:
        name = name.strip()
        if name.endswith("ies"):
            name = name[:-3] + "y"
        elif name.endswith("ses"):
            name = name[:-2]
        elif name.endswith("s") and not name.endswith("ss"):
            name = name[:-1]
        parts = name.split("_")
        return "".join(p.capitalize() for p in parts if p)
