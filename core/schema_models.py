from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class DataType(str, Enum):
    INT = "INT"
    BIGINT = "BIGINT"
    SMALLINT = "SMALLINT"
    TINYINT = "TINYINT"
    VARCHAR = "VARCHAR"
    CHAR = "CHAR"
    TEXT = "TEXT"
    LONGTEXT = "LONGTEXT"
    BOOLEAN = "BOOLEAN"
    DECIMAL = "DECIMAL"
    FLOAT = "FLOAT"
    DOUBLE = "DOUBLE"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIMESTAMP = "TIMESTAMP"
    JSON = "JSON"
    UUID = "VARCHAR(36)"

class RelationshipType(str, Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    MANY_TO_MANY = "N:M"

class ForeignKeyConstraint(BaseModel):
    column_name: str = Field(..., description="Local column in this table")
    target_table: str = Field(..., description="Referenced parent table")
    target_column: str = Field(..., description="Referenced parent column, usually id")
    on_delete: str = Field("CASCADE", description="CASCADE, SET NULL, RESTRICT, NO ACTION")
    on_update: str = Field("CASCADE", description="CASCADE, SET NULL, RESTRICT, NO ACTION")

class IndexSchema(BaseModel):
    name: str
    columns: List[str]
    is_unique: bool = False

class ColumnSchema(BaseModel):
    name: str
    data_type: str = "VARCHAR(255)"
    length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_nullable: bool = True
    is_unique: bool = False
    auto_increment: bool = False
    default_value: Optional[str] = None
    comment: Optional[str] = None
    foreign_key_target: Optional[str] = None  # e.g., "users.id"

class TableSchema(BaseModel):
    name: str
    columns: List[ColumnSchema] = []
    primary_keys: List[str] = []
    foreign_keys: List[ForeignKeyConstraint] = []
    indexes: List[IndexSchema] = []
    comment: Optional[str] = None

    def get_column(self, col_name: str) -> Optional[ColumnSchema]:
        for col in self.columns:
            if col.name.lower() == col_name.lower():
                return col
        return None

    def get_pk_columns(self) -> List[ColumnSchema]:
        return [c for c in self.columns if c.is_primary_key or c.name in self.primary_keys]

class RelationshipSchema(BaseModel):
    source_table: str
    target_table: str
    rel_type: RelationshipType = RelationshipType.ONE_TO_MANY
    source_cardinality: str = "1"
    target_cardinality: str = "N"
    foreign_key: Optional[str] = None
    description: Optional[str] = None

class ValidationIssue(BaseModel):
    severity: str = "warning"  # "error", "warning", "info"
    table: Optional[str] = None
    column: Optional[str] = None
    message: str
    suggestion: Optional[str] = None

class ValidationResult(BaseModel):
    is_valid: bool = True
    issues: List[ValidationIssue] = []
    normalized_tables_count: int = 0
    resolved_foreign_keys_count: int = 0

class UMLAttribute(BaseModel):
    visibility: str = "+"  # +, -, #, ~
    name: str
    type_name: str
    is_static: bool = False

class UMLMethod(BaseModel):
    visibility: str = "+"
    name: str
    return_type: str = "void"
    parameters: List[str] = []
    is_static: bool = False

class UMLClass(BaseModel):
    name: str
    stereotype: Optional[str] = "Entity"
    attributes: List[UMLAttribute] = []
    methods: List[UMLMethod] = []
    extends: Optional[str] = None
    implements: List[str] = []

class UMLModel(BaseModel):
    classes: List[UMLClass] = []
    relationships: List[RelationshipSchema] = []

class DatabaseSchema(BaseModel):
    database_name: str = "schemamind_db"
    tables: List[TableSchema] = []
    relationships: List[RelationshipSchema] = []
    notes: Optional[str] = None

    def get_table(self, table_name: str) -> Optional[TableSchema]:
        for t in self.tables:
            if t.name.lower() == table_name.lower():
                return t
        return None

    def get_topological_order(self) -> List[TableSchema]:
        """
        Returns tables ordered so that parent tables come before dependent child tables.
        Essential for valid MySQL CREATE TABLE and DROP TABLE execution order.
        """
        table_map = {t.name.lower(): t for t in self.tables}
        # Build dependency graph
        deps: Dict[str, set] = {t.name.lower(): set() for t in self.tables}
        for t in self.tables:
            for fk in t.foreign_keys:
                parent = fk.target_table.lower()
                if parent in table_map and parent != t.name.lower():
                    deps[t.name.lower()].add(parent)
            # Also check columns with foreign_key_target
            for col in t.columns:
                if col.foreign_key_target and "." in col.foreign_key_target:
                    parent = col.foreign_key_target.split(".")[0].lower()
                    if parent in table_map and parent != t.name.lower():
                        deps[t.name.lower()].add(parent)

        visited = set()
        order: List[TableSchema] = []

        def visit(node: str, current_path: set):
            if node in current_path:
                # Cycle detected, break out gracefully
                return
            if node not in visited:
                current_path.add(node)
                for dep in deps.get(node, []):
                    visit(dep, current_path)
                current_path.remove(node)
                visited.add(node)
                if node in table_map:
                    order.append(table_map[node])

        for t_name in table_map:
            visit(t_name, set())

        return order
