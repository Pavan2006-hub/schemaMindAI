import logging
from typing import List, Set, Dict
from core.schema_models import (
    DatabaseSchema,
    ValidationResult,
    ValidationIssue
)

logger = logging.getLogger(__name__)

class ValidationAgent:
    """
    Validation Agent:
    Validates logical database schema consistency, verifies foreign key targets,
    flags MySQL reserved keywords, detects circular dependencies, and suggests fixes.
    """

    RESERVED_MYSQL_KEYWORDS: Set[str] = {
        "accessible", "add", "all", "alter", "analyze", "and", "as", "asc", "asensitive",
        "before", "between", "bigint", "binary", "blob", "both", "by", "call", "cascade",
        "case", "change", "char", "character", "check", "collate", "column", "condition",
        "constraint", "continue", "convert", "create", "cross", "current_date", "current_time",
        "current_timestamp", "current_user", "cursor", "database", "databases", "day_hour",
        "day_microsecond", "day_minute", "day_second", "dec", "decimal", "declare", "default",
        "delayed", "delete", "desc", "describe", "deterministic", "distinct", "distinctrow",
        "div", "double", "drop", "dual", "each", "else", "elseif", "enclosed", "escaped",
        "exists", "exit", "explain", "false", "fetch", "float", "float4", "float8", "for",
        "force", "foreign", "from", "fulltext", "grant", "group", "having", "high_priority",
        "hour_microsecond", "hour_minute", "hour_second", "if", "ignore", "in", "index",
        "infile", "inner", "inout", "insensitive", "insert", "int", "int1", "int2", "int3",
        "int4", "int8", "integer", "interval", "into", "is", "iterate", "join", "key",
        "keys", "kill", "leading", "leave", "left", "like", "limit", "linear", "lines",
        "load", "localtime", "localtimestamp", "lock", "long", "longblob", "longtext",
        "loop", "low_priority", "master_ssl_verify_server_cert", "match", "maxvalue",
        "mediumblob", "mediumint", "mediumtext", "middleint", "minute_microsecond",
        "minute_second", "mod", "modifies", "natural", "not", "no_write_to_binlog",
        "null", "numeric", "on", "optimize", "option", "optionally", "or", "order",
        "out", "outer", "outfile", "precision", "primary", "procedure", "purge", "range",
        "read", "reads", "read_write", "real", "references", "regexp", "release", "rename",
        "repeat", "replace", "require", "resignal", "restrict", "return", "revoke",
        "right", "rlike", "schema", "schemas", "second_microsecond", "select", "sensitive",
        "separator", "set", "show", "signal", "smallint", "spatial", "specific", "sql",
        "sqlexception", "sqlstate", "sqlwarning", "sql_big_result", "sql_calc_found_rows",
        "sql_small_result", "ssl", "starting", "straight_join", "table", "terminated",
        "then", "tinyblob", "tinyint", "tinytext", "to", "trailing", "trigger", "true",
        "undo", "union", "unique", "unlock", "unsigned", "update", "usage", "use",
        "using", "utc_date", "utc_time", "utc_timestamp", "values", "varbinary",
        "varchar", "varcharacter", "varying", "when", "where", "while", "with",
        "write", "xor", "year_month", "zerofill"
    }

    def validate(self, schema: DatabaseSchema) -> ValidationResult:
        """
        Runs comprehensive consistency, relational, and keyword checks on the database schema.
        """
        issues: List[ValidationIssue] = []
        table_map = {t.name.lower(): t for t in schema.tables}

        # 1. Table-level checks
        for table in schema.tables:
            # Check reserved keyword for table name
            if table.name.lower() in self.RESERVED_MYSQL_KEYWORDS:
                issues.append(ValidationIssue(
                    severity="warning",
                    table=table.name,
                    message=f"Table name '{table.name}' is a reserved MySQL keyword.",
                    suggestion=f"Enclose `{table.name}` in backticks or rename to `{table.name}s`."
                ))

            # Check primary key existence
            if not table.primary_keys:
                issues.append(ValidationIssue(
                    severity="error",
                    table=table.name,
                    message=f"Table '{table.name}' does not have a Primary Key defined.",
                    suggestion=f"Add an auto-incrementing 'id' BIGINT Primary Key."
                ))

            # Column-level checks
            col_names = set()
            for col in table.columns:
                # Duplicate column check
                if col.name.lower() in col_names:
                    issues.append(ValidationIssue(
                        severity="error",
                        table=table.name,
                        column=col.name,
                        message=f"Duplicate column name '{col.name}' found in table '{table.name}'."
                    ))
                col_names.add(col.name.lower())

                # Reserved keyword column check
                if col.name.lower() in self.RESERVED_MYSQL_KEYWORDS:
                    issues.append(ValidationIssue(
                        severity="warning",
                        table=table.name,
                        column=col.name,
                        message=f"Column name '{col.name}' is a reserved MySQL keyword.",
                        suggestion=f"Enclose in backticks `{col.name}` in SQL queries."
                    ))

            # Foreign key integrity check
            for fk in table.foreign_keys:
                parent_table_name = fk.target_table.lower()
                if parent_table_name not in table_map:
                    issues.append(ValidationIssue(
                        severity="error",
                        table=table.name,
                        column=fk.column_name,
                        message=f"Foreign key '{fk.column_name}' references non-existent table '{fk.target_table}'."
                    ))
                else:
                    parent_table = table_map[parent_table_name]
                    target_col = parent_table.get_column(fk.target_column)
                    if not target_col:
                        issues.append(ValidationIssue(
                            severity="error",
                            table=table.name,
                            column=fk.column_name,
                            message=f"Foreign key '{fk.column_name}' references non-existent column '{fk.target_column}' in table '{fk.target_table}'."
                        ))
                    else:
                        local_col = table.get_column(fk.column_name)
                        if local_col and local_col.data_type.split("(")[0] != target_col.data_type.split("(")[0]:
                            issues.append(ValidationIssue(
                                severity="warning",
                                table=table.name,
                                column=fk.column_name,
                                message=f"Data type mismatch: '{table.name}.{local_col.name}' is {local_col.data_type} but references '{fk.target_table}.{target_col.name}' ({target_col.data_type}).",
                                suggestion=f"Align '{table.name}.{local_col.name}' type to {target_col.data_type}."
                            ))

        # Check for circular foreign keys
        cycles = self._detect_circular_dependencies(schema)
        for cycle in cycles:
            issues.append(ValidationIssue(
                severity="warning",
                message=f"Circular foreign key dependency detected: {' -> '.join(cycle)}.",
                suggestion="Consider resolving with a junction table or creating foreign key constraints via ALTER TABLE after table creation."
            ))

        has_errors = any(issue.severity == "error" for issue in issues)
        resolved_fks = sum(len(t.foreign_keys) for t in schema.tables)

        return ValidationResult(
            is_valid=not has_errors,
            issues=issues,
            normalized_tables_count=len(schema.tables),
            resolved_foreign_keys_count=resolved_fks
        )

    def _detect_circular_dependencies(self, schema: DatabaseSchema) -> List[List[str]]:
        """Finds any circular FK relationships."""
        table_map = {t.name.lower(): t for t in schema.tables}
        adj: Dict[str, List[str]] = {t.name.lower(): [] for t in schema.tables}
        for t in schema.tables:
            for fk in t.foreign_keys:
                if fk.target_table.lower() in table_map and fk.target_table.lower() != t.name.lower():
                    adj[t.name.lower()].append(fk.target_table.lower())

        visited = set()
        stack: List[str] = []
        cycles: List[List[str]] = []

        def dfs(node: str):
            if node in stack:
                cycle_slice = stack[stack.index(node):] + [node]
                cycles.append(cycle_slice)
                return
            if node in visited:
                return

            visited.add(node)
            stack.append(node)
            for neighbor in adj.get(node, []):
                dfs(neighbor)
            stack.pop()

        for t_name in table_map:
            dfs(t_name)

        return cycles

    def auto_repair(self, schema: DatabaseSchema, validation: ValidationResult) -> DatabaseSchema:
        """
        Automatically fixes errors and discrepancies where possible.
        """
        table_map = {t.name.lower(): t for t in schema.tables}

        for issue in validation.issues:
            if issue.severity == "error" and issue.table:
                table = table_map.get(issue.table.lower())
                if table and not table.primary_keys:
                    # Add missing primary key
                    table.columns.insert(0, ColumnSchema(
                        name="id",
                        data_type="BIGINT",
                        is_primary_key=True,
                        is_nullable=False,
                        auto_increment=True
                    ))
                    table.primary_keys.append("id")
                    logger.info(f"[ValidationAgent] Repaired table '{table.name}' by inserting primary key 'id'.")

        return schema
