from typing import List
from core.schema_models import DatabaseSchema, TableSchema, RelationshipSchema

class ERDGenerator:
    """
    ERD Generator:
    Converts normalized database schemas into standard Mermaid ER diagrams
    and Graphviz DOT format.
    """

    def generate_mermaid_erd(self, schema: DatabaseSchema) -> str:
        """
        Generates Mermaid ERD specification.
        """
        lines: List[str] = ["erDiagram"]

        # 1. Output relationships
        for rel in schema.relationships:
            src = rel.source_table.upper()
            tgt = rel.target_table.upper()

            # Map cardinality to Mermaid syntax
            # ||--o{ = one to zero-or-more
            # ||--|{ = one to many
            # ||--|| = one to one
            # }o--o{ = many to many
            if rel.rel_type.value == "1:1":
                connector = "||--||"
            elif rel.rel_type.value == "1:N":
                connector = "||--o{"
            elif rel.rel_type.value == "N:1":
                connector = "}o--||"
            elif rel.rel_type.value == "N:M":
                connector = "}o--o{"
            else:
                connector = "||--o{"

            label = rel.description or rel.foreign_key or "relates"
            lines.append(f"    {src} {connector} {tgt} : \"{label}\"")

        # 2. Output table definitions
        for table in schema.tables:
            tbl_name = table.name.upper()
            lines.append(f"    {tbl_name} {{")
            for col in table.columns:
                # Mermaid ERD format: type name [PK|FK|UK] ["comment"]
                col_type = col.data_type.lower().replace(" ", "_").replace("(", "_").replace(")", "").replace(",", "_")
                flags = []
                if col.is_primary_key:
                    flags.append("PK")
                if col.is_foreign_key:
                    flags.append("FK")
                if col.is_unique and not col.is_primary_key:
                    flags.append("UK")

                flag_str = " ".join(flags)
                comment_str = f' "{col.comment}"' if col.comment else ""
                lines.append(f"        {col_type} {col.name} {flag_str}{comment_str}".rstrip())
            lines.append("    }")

        return "\n".join(lines)

    def generate_graphviz(self, schema: DatabaseSchema) -> str:
        """
        Generates Graphviz DOT representation of the ER diagram.
        """
        lines = [
            "digraph ERD {",
            "    rankdir=LR;",
            "    node [shape=record, fontname=\"Helvetica\", fontsize=10];",
            "    edge [fontname=\"Helvetica\", fontsize=9];",
            ""
        ]

        for table in schema.tables:
            fields = []
            for col in table.columns:
                prefix = "+ " if col.is_primary_key else ("# " if col.is_foreign_key else "  ")
                fields.append(f"{prefix}{col.name}: {col.data_type}")
            label = f"{{{table.name}|" + "\\l".join(fields) + "\\l}"
            lines.append(f'    "{table.name}" [label="{label}"];')

        lines.append("")
        for rel in schema.relationships:
            label = rel.rel_type.value
            lines.append(f'    "{rel.source_table}" -> "{rel.target_table}" [label="{label}"];')

        lines.append("}")
        return "\n".join(lines)
