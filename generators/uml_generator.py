from typing import List
from core.schema_models import UMLModel, UMLClass

class UMLGenerator:
    """
    UML Generator:
    Generates Mermaid Class Diagrams, PlantUML representations,
    and Architectural Sequence Diagrams.
    """

    def generate_mermaid_class_diagram(self, model: UMLModel) -> str:
        """
        Generates Mermaid syntax for UML Class diagram.
        """
        lines: List[str] = ["classDiagram"]

        # Relationships
        for rel in model.relationships:
            src = self._to_pascal(rel.source_table)
            tgt = self._to_pascal(rel.target_table)
            # Association arrows
            lines.append(f"    {src} \"1\" --> \"*\" {tgt} : manages")

        # Class specifications
        for cls in model.classes:
            lines.append(f"    class {cls.name} {{")
            if cls.stereotype:
                lines.append(f"        <<{cls.stereotype}>>")

            for attr in cls.attributes:
                lines.append(f"        {attr.visibility}{attr.type_name} {attr.name}")

            for m in cls.methods:
                params_str = ", ".join(m.parameters)
                lines.append(f"        {m.visibility}{m.name}({params_str}) {m.return_type}")

            lines.append("    }")

        return "\n".join(lines)

    def generate_plantuml(self, model: UMLModel) -> str:
        """
        Generates PlantUML script (@startuml ... @enduml).
        """
        lines: List[str] = [
            "@startuml",
            "skinparam classAttributeIconSize 0",
            "skinparam style strictuml",
            "skinparam shadowing false",
            "skinparam class {",
            "    BackgroundColor White",
            "    ArrowColor #2b6cb0",
            "    BorderColor #2b6cb0",
            "}",
            ""
        ]

        # Classes
        for cls in model.classes:
            lines.append(f"class {cls.name} <<{cls.stereotype}>> {{")
            for attr in cls.attributes:
                lines.append(f"  {attr.visibility} {attr.name}: {attr.type_name}")
            lines.append("  --")
            for m in cls.methods:
                params_str = ", ".join(m.parameters)
                lines.append(f"  {m.visibility} {m.name}({params_str}): {m.return_type}")
            lines.append("}")
            lines.append("")

        # Associations
        for rel in model.relationships:
            src = self._to_pascal(rel.source_table)
            tgt = self._to_pascal(rel.target_table)
            lines.append(f'{src} "1" *-- "*" {tgt} : has >')

        lines.append("@enduml")
        return "\n".join(lines)

    def generate_sequence_diagram(self, model: UMLModel) -> str:
        """
        Generates a Mermaid sequence diagram illustrating typical domain transaction flows.
        """
        if not model.classes:
            return "sequenceDiagram\n    Client->>Server: Request\n    Server-->>Client: Response"

        main_entity = model.classes[0].name
        secondary_entity = model.classes[1].name if len(model.classes) > 1 else "AuditLog"

        lines = [
            "sequenceDiagram",
            "    autonumber",
            "    actor User",
            f"    participant UI as WebApp UI",
            f"    participant API as {main_entity}Controller",
            f"    participant Svc as {main_entity}Service",
            f"    participant Repo as {main_entity}Repository",
            f"    participant DB as MySQL Database",
            "",
            f"    User->>UI: Submit Create {main_entity} Form",
            f"    UI->>API: POST /api/{main_entity.lower()}s (Payload JSON)",
            f"    API->>Svc: create{main_entity}(DTO)",
            f"    activate Svc",
            f"    Svc->>Svc: Validate Business Rules",
            f"    Svc->>Repo: save(entity)",
            f"    activate Repo",
            f"    Repo->>DB: INSERT INTO {main_entity.lower()}s (data...)",
            f"    DB-->>Repo: 201 Created (ID generated)",
            f"    deactivate Repo",
            f"    Svc-->>API: {main_entity} Response DTO",
            f"    deactivate Svc",
            f"    API-->>UI: HTTP 201 Created",
            f"    UI-->>User: Display Success Confirmation"
        ]
        return "\n".join(lines)

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
