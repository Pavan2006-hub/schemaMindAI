import re
from typing import List, Dict, Any

class SQLValidator:
    """
    SQL Validator:
    Verifies that the generated MySQL script has valid syntax, balanced delimiters,
    no illegal trailing commas, and correct engine declarations.
    """

    def validate_sql(self, sql_script: str) -> Dict[str, Any]:
        issues: List[str] = []

        # 1. Balanced parentheses check
        open_paren = sql_script.count("(")
        close_paren = sql_script.count(")")
        if open_paren != close_paren:
            issues.append(f"Mismatched parentheses: found {open_paren} '(' and {close_paren} ')'.")

        # 2. Balanced backticks check
        backticks = sql_script.count("`")
        if backticks % 2 != 0:
            issues.append(f"Unpaired backtick character detected in SQL script (total: {backticks}).")

        # 3. Trailing commas before closing parentheses (common MySQL syntax blunder)
        trailing_comma_match = re.search(r",\s*\)", sql_script)
        if trailing_comma_match:
            issues.append("Found illegal trailing comma before a closing parenthesis in CREATE TABLE statement.")

        # 4. Check for CREATE TABLE without ENGINE
        create_tables = re.findall(r"CREATE TABLE [`\w]+", sql_script, re.IGNORECASE)
        engine_matches = re.findall(r"ENGINE\s*=\s*InnoDB", sql_script, re.IGNORECASE)
        if len(create_tables) != len(engine_matches):
            issues.append("Some CREATE TABLE statements are missing explicit 'ENGINE=InnoDB' declarations.")

        return {
            "is_valid": len(issues) == 0,
            "errors": issues,
            "table_count": len(create_tables)
        }
