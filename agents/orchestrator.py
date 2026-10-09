import time
import logging
from typing import Dict, Any, Optional
from core.gemma_client import GemmaClient
from core.workflow import WorkflowState, StepStatus
from core.schema_models import DatabaseSchema
from agents.vision_agent import VisionAgent
from agents.schema_agent import SchemaAgent
from agents.validation_agent import ValidationAgent
from agents.uml_agent import UMLAgent
from generators.erd_generator import ERDGenerator
from generators.uml_generator import UMLGenerator
from generators.mysql_generator import MySQLGenerator
from generators.python_generator import PythonGenerator

logger = logging.getLogger(__name__)

class MultiAgentOrchestrator:
    """
    Multi-Agent Orchestrator:
    Manages the lifecycle, communication protocols, and execution loops across:
    1. VisionAgent (Visual perception)
    2. SchemaAgent (Normalization & 3NF)
    3. ValidationAgent (Rule & Integrity audit with repair loop)
    4. UMLAgent (OO Domain architecture)
    5. Artifact Generators (ERD, UML, MySQL, Python ORM)
    """

    def __init__(self, gemma_client: GemmaClient, max_retries: int = 3):
        self.client = gemma_client
        self.max_retries = max_retries
        self.vision_agent = VisionAgent(gemma_client)
        self.schema_agent = SchemaAgent(gemma_client)
        self.validation_agent = ValidationAgent()
        self.uml_agent = UMLAgent(gemma_client)

        self.erd_gen = ERDGenerator()
        self.uml_gen = UMLGenerator()
        self.mysql_gen = MySQLGenerator()
        self.python_gen = PythonGenerator()

    def process_diagram(self, session_id: str, image_path: str, context_hint: Optional[str] = None) -> WorkflowState:
        """
        Executes the end-to-end multi-agent pipeline.
        """
        state = WorkflowState(session_id=session_id, image_path=image_path)
        t_start_total = time.time()

        try:
            # 1. Vision Perception Step
            t0 = time.time()
            state.add_event("Vision Perception", "VisionAgent", "Starting ER diagram visual inspection...", StepStatus.IN_PROGRESS)
            raw_data = self.vision_agent.extract_from_image(image_path, context_hint)
            state.raw_vision_output = raw_data
            duration = round((time.time() - t0) * 1000, 2)
            state.add_event(
                "Vision Perception",
                "VisionAgent",
                f"Extracted {len(raw_data.get('tables', []))} raw entities from diagram image.",
                StepStatus.COMPLETED,
                duration
            )

            # 2. Schema Normalization & Constraint Resolution Step
            t0 = time.time()
            state.add_event("Schema Normalization", "SchemaAgent", "Normalizing tables, data types, and foreign keys...", StepStatus.IN_PROGRESS)
            schema: DatabaseSchema = self.schema_agent.normalize_schema(raw_data)
            duration = round((time.time() - t0) * 1000, 2)
            state.add_event(
                "Schema Normalization",
                "SchemaAgent",
                f"Normalized schema '{schema.database_name}' with {len(schema.tables)} tables and {len(schema.relationships)} relations.",
                StepStatus.COMPLETED,
                duration
            )

            # 3. Validation & Iterative Refinement Loop
            t0 = time.time()
            state.add_event("Schema Validation", "ValidationAgent", "Running integrity and SQL reserved keyword audit...", StepStatus.IN_PROGRESS)
            val_result = self.validation_agent.validate(schema)

            iteration = 0
            while not val_result.is_valid and iteration < self.max_retries:
                iteration += 1
                state.refinement_iterations = iteration
                state.add_event(
                    "Refinement Loop",
                    "ValidationAgent",
                    f"Attempting automated repair iteration {iteration} of {self.max_retries}...",
                    StepStatus.IN_PROGRESS
                )
                schema = self.validation_agent.auto_repair(schema, val_result)
                val_result = self.validation_agent.validate(schema)

            state.database_schema = schema.model_dump()
            state.validation_result = val_result.model_dump()
            duration = round((time.time() - t0) * 1000, 2)
            val_status = StepStatus.COMPLETED if val_result.is_valid else StepStatus.FAILED
            state.add_event(
                "Schema Validation",
                "ValidationAgent",
                f"Validation finished. {len(val_result.issues)} issues identified ({sum(1 for i in val_result.issues if i.severity == 'error')} errors).",
                val_status,
                duration
            )

            # 4. UML Modeling Step
            t0 = time.time()
            state.add_event("UML Architecture", "UMLAgent", "Transforming relational schema to Domain Classes and Methods...", StepStatus.IN_PROGRESS)
            uml_model = self.uml_agent.generate_uml_model(schema)
            duration = round((time.time() - t0) * 1000, 2)
            state.add_event(
                "UML Architecture",
                "UMLAgent",
                f"Generated domain model with {len(uml_model.classes)} UML classes.",
                StepStatus.COMPLETED,
                duration
            )

            # 5. Multi-Artifact Generation Step
            t0 = time.time()
            state.add_event("Artifact Generation", "Generators", "Generating ERD, UML, MySQL SQL, and Python code...", StepStatus.IN_PROGRESS)

            erd_mermaid = self.erd_gen.generate_mermaid_erd(schema)
            erd_dot = self.erd_gen.generate_graphviz(schema)
            uml_mermaid = self.uml_gen.generate_mermaid_class_diagram(uml_model)
            uml_plantuml = self.uml_gen.generate_plantuml(uml_model)
            uml_sequence = self.uml_gen.generate_sequence_diagram(uml_model)
            mysql_sql = self.mysql_gen.generate_sql(schema)
            sqlalchemy_code = self.python_gen.generate_sqlalchemy_models(schema)
            pydantic_code = self.python_gen.generate_pydantic_schemas(schema)
            fastapi_code = self.python_gen.generate_fastapi_endpoints(schema)

            state.generated_artifacts = {
                "erd_mermaid": erd_mermaid,
                "erd_dot": erd_dot,
                "uml_mermaid": uml_mermaid,
                "uml_plantuml": uml_plantuml,
                "uml_sequence": uml_sequence,
                "mysql_sql": mysql_sql,
                "sqlalchemy_code": sqlalchemy_code,
                "pydantic_code": pydantic_code,
                "fastapi_code": fastapi_code
            }

            duration = round((time.time() - t0) * 1000, 2)
            total_duration = round((time.time() - t_start_total) * 1000, 2)
            state.add_event(
                "Artifact Generation",
                "Generators",
                f"Generated all target artifacts successfully in {duration}ms (Total pipeline: {total_duration}ms).",
                StepStatus.COMPLETED,
                duration
            )

        except Exception as e:
            logger.exception(f"Pipeline error for session {session_id}: {e}")
            state.error_message = str(e)
            state.add_event("Pipeline Execution", "Orchestrator", f"Pipeline error: {str(e)}", StepStatus.FAILED)

        return state
