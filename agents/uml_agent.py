import re
import logging
from typing import List, Dict, Any
from core.schema_models import (
    DatabaseSchema,
    TableSchema,
    UMLModel,
    UMLClass,
    UMLAttribute,
    UMLMethod,
    RelationshipSchema
)
from core.gemma_client import GemmaClient

logger = logging.getLogger(__name__)

class UMLAgent:
    """
    UML Architect Agent:
    Transforms normalized relational database schemas into Object-Oriented Domain Models,
    producing Class Diagrams, Domain Methods, and Architectural Associations.
    """

    SQL_TO_UML_TYPE = {
        "BIGINT": "Long",
        "INT": "Integer",
        "SMALLINT": "Integer",
        "TINYINT": "Integer",
        "BOOLEAN": "Boolean",
        "VARCHAR": "String",
        "CHAR": "String",
        "TEXT": "String",
        "LONGTEXT": "String",
        "DECIMAL": "BigDecimal",
        "FLOAT": "Float",
        "DOUBLE": "Double",
        "DATE": "LocalDate",
        "DATETIME": "LocalDateTime",
        "TIMESTAMP": "Instant",
        "JSON": "Map<String, Object>"
    }

    def __init__(self, gemma_client: GemmaClient):
        self.client = gemma_client

    def generate_uml_model(self, schema: DatabaseSchema) -> UMLModel:
        """
        Converts the relational schema into an object-oriented domain UML model.
        """
        classes: List[UMLClass] = []

        for table in schema.tables:
            class_name = self._to_singular_pascal_case(table.name)
            attributes: List[UMLAttribute] = []
            methods: List[UMLMethod] = []

            for col in table.columns:
                uml_type = self._map_sql_to_uml_type(col.data_type)
                attr_name = self._to_camel_case(col.name)
                attributes.append(
                    UMLAttribute(
                        visibility="-",  # private by standard OOP encapsulation
                        name=attr_name,
                        type_name=uml_type
                    )
                )

            # Generate standard Domain / Active Record & Repository methods
            pk_col = table.primary_keys[0] if table.primary_keys else "id"
            pk_type = "Long" if "BIGINT" in table.get_column(pk_col).data_type.upper() else "Integer"

            methods.append(UMLMethod(visibility="+", name=f"findById", return_type=class_name, parameters=[f"id: {pk_type}"], is_static=True))
            methods.append(UMLMethod(visibility="+", name=f"save", return_type="Boolean", parameters=[]))
            methods.append(UMLMethod(visibility="+", name=f"delete", return_type="Boolean", parameters=[]))

            # Add domain-specific behavioral methods
            table_lower = table.name.lower()
            if "user" in table_lower or "account" in table_lower:
                methods.append(UMLMethod(visibility="+", name="authenticate", return_type="Boolean", parameters=["token: String"]))
            elif "order" in table_lower:
                methods.append(UMLMethod(visibility="+", name="calculateTotal", return_type="BigDecimal", parameters=[]))
                methods.append(UMLMethod(visibility="+", name="processPayment", return_type="Boolean", parameters=[]))
            elif "product" in table_lower or "item" in table_lower:
                methods.append(UMLMethod(visibility="+", name="isInStock", return_type="Boolean", parameters=[]))
                methods.append(UMLMethod(visibility="+", name="updateQuantity", return_type="void", parameters=["qty: Integer"]))

            classes.append(
                UMLClass(
                    name=class_name,
                    stereotype="Entity",
                    attributes=attributes,
                    methods=methods
                )
            )

        return UMLModel(
            classes=classes,
            relationships=schema.relationships
        )

    def _map_sql_to_uml_type(self, sql_type: str) -> str:
        base_type = sql_type.split("(")[0].strip().upper()
        return self.SQL_TO_UML_TYPE.get(base_type, "String")

    @staticmethod
    def _to_singular_pascal_case(name: str) -> str:
        """Converts plural snake_case table name to Singular PascalCase."""
        name = name.strip()
        # Simple singularization
        if name.endswith("ies"):
            name = name[:-3] + "y"
        elif name.endswith("ses"):
            name = name[:-2]
        elif name.endswith("s") and not name.endswith("ss"):
            name = name[:-1]

        parts = name.split("_")
        return "".join(part.capitalize() for part in parts if part)

    @staticmethod
    def _to_camel_case(name: str) -> str:
        """Converts snake_case to camelCase."""
        parts = name.split("_")
        return parts[0].lower() + "".join(part.capitalize() for part in parts[1:])
