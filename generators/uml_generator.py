import re
from typing import List
from core.schema_models import UMLModel


class UMLGenerator:
    """
    Generates Mermaid class diagrams, PlantUML class diagrams,
    and Mermaid sequence diagrams.
    """

    # --------------------------------------------------
    # Naming and escaping helpers
    # --------------------------------------------------

    @staticmethod
    def _to_pascal(name: str) -> str:
        """Convert table names into valid, consistent class identifiers."""
        name = str(name or "").strip()

        if name.endswith("ies"):
            name = name[:-3] + "y"
        elif name.endswith("ses"):
            name = name[:-2]
        elif name.endswith("s") and not name.endswith("ss"):
            name = name[:-1]

        parts = re.split(r"[^a-zA-Z0-9]+", name)
        result = "".join(part[:1].upper() + part[1:] for part in parts if part)

        if not result:
            return "UnnamedClass"

        if result[0].isdigit():
            result = "Entity" + result

        return result

    @staticmethod
    def _safe_text(value: object) -> str:
        """Remove newlines and Mermaid-breaking braces from labels."""
        text = str(value or "")
        text = text.replace("\r", " ").replace("\n", " ")
        text = text.replace("{", "(").replace("}", ")")
        return text.strip()

    @classmethod
    def _safe_identifier(cls, value: object) -> str:
        """Create a Mermaid-safe identifier."""
        text = cls._safe_text(value)
        text = re.sub(r"[^a-zA-Z0-9_]", "_", text)

        if not text:
            return "unnamed"

        if text[0].isdigit():
            text = "field_" + text

        return text

    @classmethod
    def _safe_type(cls, value: object) -> str:
        """Normalize a type for display in a diagram."""
        text = cls._safe_text(value)
        return text or "String"

    @staticmethod
    def _visibility(value: object) -> str:
        """Normalize UML visibility to Mermaid's supported symbols."""
        value = str(value or "+").strip()

        if value in ("+", "-", "#", "~"):
            return value

        mapping = {
            "public": "+",
            "private": "-",
            "protected": "#",
            "package": "~",
        }

        return mapping.get(value.lower(), "+")

    # --------------------------------------------------
    # Mermaid class diagram
    # --------------------------------------------------

    def generate_mermaid_class_diagram(self, model: UMLModel) -> str:
        lines: List[str] = ["classDiagram"]

        # Build one consistent mapping for relationship endpoints.
        class_names = {
            str(cls.name): self._to_pascal(cls.name)
            for cls in model.classes
        }

        available_names = set(class_names.values())

        # Relationships
        for rel in model.relationships:
            source = class_names.get(
                str(rel.source_table),
                self._to_pascal(rel.source_table)
            )
            target = class_names.get(
                str(rel.target_table),
                self._to_pascal(rel.target_table)
            )

            # Do not generate relationships to missing classes.
            if source not in available_names or target not in available_names:
                continue

            if source == target:
                continue

            lines.append(f'    {source} "1" --> "*" {target} : relates to')

        # Class definitions
        for cls in model.classes:
            class_name = class_names[str(cls.name)]
            lines.append(f"    class {class_name} {{")

            stereotype = self._safe_text(getattr(cls, "stereotype", ""))
            if stereotype:
                stereotype = re.sub(r"[^a-zA-Z0-9_ -]", "", stereotype)
                if stereotype:
                    lines.append(f"        <<{stereotype}>>")

            # Attributes: visibility name : type
            for attr in cls.attributes:
                visibility = self._visibility(
                    getattr(attr, "visibility", "+")
                )
                name = self._safe_identifier(
                    getattr(attr, "name", "field")
                )
                type_name = self._safe_type(
                    getattr(attr, "type_name", "String")
                )

                lines.append(
                    f"        {visibility}{name} : {type_name}"
                )

            # Methods: visibility method(parameters) returnType
            for method in cls.methods:
                visibility = self._visibility(
                    getattr(method, "visibility", "+")
                )
                method_name = self._safe_identifier(
                    getattr(method, "name", "operation")
                )

                parameters = getattr(method, "parameters", []) or []
                safe_parameters = [
                    self._safe_text(parameter).replace(",", " ")
                    for parameter in parameters
                ]
                params_str = ", ".join(
                    parameter for parameter in safe_parameters if parameter
                )

                return_type = self._safe_type(
                    getattr(method, "return_type", "void")
                )

                lines.append(
                    f"        {visibility}{method_name}({params_str}) : {return_type}"
                )

            lines.append("    }")

        return "\n".join(lines)

    # --------------------------------------------------
    # PlantUML class diagram
    # --------------------------------------------------

    def generate_plantuml(self, model: UMLModel) -> str:
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
            "",
        ]

        class_names = {
            str(cls.name): self._to_pascal(cls.name)
            for cls in model.classes
        }

        available_names = set(class_names.values())

        for cls in model.classes:
            class_name = class_names[str(cls.name)]
            stereotype = self._safe_text(
                getattr(cls, "stereotype", "")
            )

            if stereotype:
                stereotype = re.sub(r"[^a-zA-Z0-9_ -]", "", stereotype)
                lines.append(f"class {class_name} <<{stereotype}>> {{")
            else:
                lines.append(f"class {class_name} {{")

            for attr in cls.attributes:
                visibility = self._visibility(
                    getattr(attr, "visibility", "+")
                )
                name = self._safe_identifier(
                    getattr(attr, "name", "field")
                )
                type_name = self._safe_type(
                    getattr(attr, "type_name", "String")
                )
                lines.append(f"  {visibility}{name}: {type_name}")

            if cls.attributes and cls.methods:
                lines.append("  --")

            for method in cls.methods:
                visibility = self._visibility(
                    getattr(method, "visibility", "+")
                )
                method_name = self._safe_identifier(
                    getattr(method, "name", "operation")
                )
                parameters = getattr(method, "parameters", []) or []
                params_str = ", ".join(
                    self._safe_text(parameter)
                    for parameter in parameters
                    if self._safe_text(parameter)
                )
                return_type = self._safe_type(
                    getattr(method, "return_type", "void")
                )

                lines.append(
                    f"  {visibility}{method_name}({params_str}): {return_type}"
                )

            lines.append("}")
            lines.append("")

        for rel in model.relationships:
            source = class_names.get(str(rel.source_table))
            target = class_names.get(str(rel.target_table))

            if (
                source in available_names
                and target in available_names
                and source != target
            ):
                lines.append(f'{source} "1" --> "*" {target} : relates to')

        lines.append("@enduml")
        return "\n".join(lines)

    # --------------------------------------------------
    # Mermaid sequence diagram
    # --------------------------------------------------

    def generate_sequence_diagram(self, model: UMLModel) -> str:
        if not model.classes:
            return (
                "sequenceDiagram\n"
                "    participant Client\n"
                "    participant Server\n"
                "    Client->>Server: Request\n"
                "    Server-->>Client: Response"
            )

        main_entity = self._to_pascal(model.classes[0].name)
        lines = [
            "sequenceDiagram",
            "    autonumber",
            "    actor User",
            "    participant UI as WebApp UI",
            f"    participant API as {main_entity}Controller",
            f"    participant Svc as {main_entity}Service",
            f"    participant Repo as {main_entity}Repository",
            "    participant DB as MySQL Database",
            "",
            f"    User->>UI: Submit {main_entity} form",
            f"    UI->>API: Send create request",
            f"    API->>Svc: Create {main_entity}",
            "    activate Svc",
            "    Svc->>Svc: Validate business rules",
            "    Svc->>Repo: Save entity",
            "    activate Repo",
            "    Repo->>DB: Insert record",
            "    DB-->>Repo: Return generated ID",
            "    deactivate Repo",
            f"    Svc-->>API: Return {main_entity} response",
            "    deactivate Svc",
            "    API-->>UI: Return success response",
            "    UI-->>User: Display confirmation",
        ]

        return "\n".join(lines)

