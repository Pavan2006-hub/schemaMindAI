import re
from typing import List
from core.schema_models import DatabaseSchema, ValidationResult, ValidationIssue

class SchemaValidator:
    """
    Schema Validator:
    Inspects database models for structural anomalies, orphaned foreign keys,
    missing primary keys, and naming violations.
    """

    def validate_schema(self, schema: DatabaseSchema) -> ValidationResult:
        issues: List[ValidationIssue] = []
        table_names = {t.name.lower() for t in schema.tables}

        # Check at least one table exists
        if not schema.tables:
            issues.append(ValidationIssue(
                severity="error",
                message="Database schema does not contain any tables."
            ))
            return ValidationResult(is_valid=False, issues=issues)

        for table in schema.tables:
            # 1. Primary Key check
            if not table.primary_keys:
                issues.append(ValidationIssue(
                    severity="error",
                    table=table.name,
                    message=f"Table '{table.name}' lacks a primary key.",
                    suggestion="Add a primary key named 'id' of type BIGINT AUTO_INCREMENT."
                ))

            # 2. Check column count
            if len(table.columns) == 0:
                issues.append(ValidationIssue(
                    severity="error",
                    table=table.name,
                    message=f"Table '{table.name}' has no columns defined."
                ))

            # 3. Foreign key target verification
            for fk in table.foreign_keys:
                if fk.target_table.lower() not in table_names:
                    issues.append(ValidationIssue(
                        severity="error",
                        table=table.name,
                        column=fk.column_name,
                        message=f"Foreign key in table '{table.name}' references non-existent parent table '{fk.target_table}'."
                    ))

            # 4. Check naming conventions
            if not re.match(r"^[a-z][a-z0-9_]*$", table.name):
                issues.append(ValidationIssue(
                    severity="warning",
                    table=table.name,
                    message=f"Table name '{table.name}' should adhere to snake_case naming conventions.",
                    suggestion=f"Convert to snake_case."
                ))

        has_errors = any(i.severity == "error" for i in issues)
        return ValidationResult(
            is_valid=not has_errors,
            issues=issues,
            normalized_tables_count=len(schema.tables),
            resolved_foreign_keys_count=sum(len(t.foreign_keys) for t in schema.tables)
        )
