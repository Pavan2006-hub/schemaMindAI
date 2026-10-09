import os
from typing import Dict

class DiagramRenderer:
    """
    Diagram Renderer:
    Prepares standalone HTML snippets and saves diagram files.
    """

    @staticmethod
    def save_diagram_files(output_dir: str, artifacts: Dict[str, str], prefix: str = "schemamind") -> Dict[str, str]:
        """
        Saves all generated code and diagrams to disk.
        """
        os.makedirs(output_dir, exist_ok=True)
        saved_paths = {}

        file_mappings = {
            "erd_mermaid": f"{prefix}_erd.mmd",
            "erd_dot": f"{prefix}_erd.dot",
            "uml_mermaid": f"{prefix}_uml.mmd",
            "uml_plantuml": f"{prefix}_uml.puml",
            "uml_sequence": f"{prefix}_sequence.mmd",
            "mysql_sql": f"{prefix}_schema.sql",
            "sqlalchemy_code": f"{prefix}_models.py",
            "pydantic_code": f"{prefix}_schemas.py",
            "fastapi_code": f"{prefix}_api.py"
        }

        for key, filename in file_mappings.items():
            content = artifacts.get(key)
            if content:
                file_path = os.path.join(output_dir, filename)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                saved_paths[key] = file_path

        return saved_paths
