import os
import uuid
import json
import zipfile
import io
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify

from config import Config
from core.gemma_client import GemmaClient
from core.image_processor import ImageProcessor
from agents.orchestrator import MultiAgentOrchestrator
from core.schema_models import DatabaseSchema
from generators.diagram_renderer import DiagramRenderer
from generators.erd_generator import ERDGenerator
from generators.uml_generator import UMLGenerator
from generators.mysql_generator import MySQLGenerator
from generators.python_generator import PythonGenerator
from agents.uml_agent import UMLAgent
from validators.schema_validator import SchemaValidator

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SchemaMindAI")

app = Flask(__name__)
app.config.from_object(Config)
Config.ensure_directories()

# Initialize Gemma Client & Orchestrator
gemma_client = GemmaClient(
    provider=Config.LLM_PROVIDER,
    model_name=Config.GEMMA_MODEL,
    base_url=Config.OLLAMA_BASE_URL,
    timeout=Config.REQUEST_TIMEOUT
)
orchestrator = MultiAgentOrchestrator(gemma_client, max_retries=Config.MAX_VALIDATION_RETRIES)

# In-memory store for session states (suitable for hackathon workflows)
SESSIONS = {}

@app.route("/")
def index():
    return render_template("index.html", config=Config)

@app.route("/upload", methods=["POST"])
def upload():
    if "diagram_file" not in request.files:
        flash("No file uploaded. Please choose an ER diagram image.", "warning")
        return redirect(url_for("index"))

    file = request.files["diagram_file"]

    if not file.filename:
        flash("No file selected.", "warning")
        return redirect(url_for("index"))

    if not ImageProcessor.allowed_file(
        file.filename, Config.ALLOWED_EXTENSIONS
    ):
        flash(
            f"Unsupported file format. Allowed: "
            f"{', '.join(Config.ALLOWED_EXTENSIONS)}",
            "danger",
        )
        return redirect(url_for("index"))

    session_id = str(uuid.uuid4())[:8]
    ext = file.filename.rsplit(".", 1)[1].lower()
    saved_filename = f"{session_id}_diagram.{ext}"
    saved_path = os.path.join(Config.UPLOAD_FOLDER, saved_filename)

    file.save(saved_path)

    domain_hint = request.form.get("domain_hint", "").strip()
    action = request.form.get("action", "full_pipeline")

    try:
        if action == "review_first":
            logger.info("[%s] Starting Vision Agent review", session_id)

            raw_vision = orchestrator.vision_agent.extract_from_image(
                saved_path, domain_hint
            )
            schema = orchestrator.schema_agent.normalize_schema(raw_vision)

            SESSIONS[session_id] = {
                "session_id": session_id,
                "image_path": saved_path,
                "schema": schema,
                "domain_hint": domain_hint,
            }

            return redirect(
                url_for("review_schema", session_id=session_id)
            )

        logger.info("[%s] Starting full multi-agent pipeline", session_id)

        state = orchestrator.process_diagram(
            session_id, saved_path, domain_hint
        )

        if not state or not getattr(state, "generated_artifacts", None):
            raise RuntimeError(
                "The pipeline finished without generating artifacts."
            )

        SESSIONS[session_id] = state

        logger.info("[%s] Pipeline completed successfully", session_id)

        return redirect(url_for("results", session_id=session_id))

    except Exception as exc:
        logger.exception("[%s] Diagram processing failed", session_id)

        # Keep a diagnostic copy of the failure for troubleshooting.
        SESSIONS[session_id] = {
            "session_id": session_id,
            "image_path": saved_path,
            "domain_hint": domain_hint,
            "error": str(exc),
        }

        if isinstance(exc, (TimeoutError,)):
            message = (
                "AI processing timed out. Check Ollama and try a smaller "
                "diagram or a faster vision model."
            )
        else:
            message = (
                f"Could not process the ER diagram: {exc}. "
                "Check the PyCharm terminal for details."
            )

        flash(message, "danger")
        return redirect(url_for("index"))


@app.route("/review/<session_id>")
def review_schema(session_id):
    session_data = SESSIONS.get(session_id)
    if not session_data:
        flash("Session expired or not found.", "warning")
        return redirect(url_for("index"))

    schema = session_data["schema"]
    schema_json = json.dumps(schema.model_dump(), indent=2)
    return render_template("review_schema.html", session_id=session_id, schema_json=schema_json)

@app.route("/approve_schema/<session_id>", methods=["POST"])
def approve_schema(session_id):
    session_data = SESSIONS.get(session_id)
    if not session_data:
        flash("Session expired.", "warning")
        return redirect(url_for("index"))

    schema_json_raw = request.form.get("schema_json", "")
    try:
        data = json.loads(schema_json_raw)
        schema = DatabaseSchema(**data)
    except Exception as e:
        flash(f"Invalid schema JSON: {str(e)}", "danger")
        return redirect(url_for("review_schema", session_id=session_id))

    # Run remaining agents and generators
    from core.workflow import WorkflowState, StepStatus
    state = WorkflowState(session_id=session_id, image_path=session_data["image_path"])
    state.database_schema = schema.model_dump()

    # Validation
    val_result = orchestrator.validation_agent.validate(schema)
    state.validation_result = val_result.model_dump()

    # UML
    uml_agent = UMLAgent(gemma_client)
    uml_model = uml_agent.generate_uml_model(schema)

    # Generators
    erd_gen = ERDGenerator()
    uml_gen = UMLGenerator()
    mysql_gen = MySQLGenerator()
    py_gen = PythonGenerator()

    state.generated_artifacts = {
        "erd_mermaid": erd_gen.generate_mermaid_erd(schema),
        "erd_dot": erd_gen.generate_graphviz(schema),
        "uml_mermaid": uml_gen.generate_mermaid_class_diagram(uml_model),
        "uml_plantuml": uml_gen.generate_plantuml(uml_model),
        "uml_sequence": uml_gen.generate_sequence_diagram(uml_model),
        "mysql_sql": mysql_gen.generate_sql(schema),
        "sqlalchemy_code": py_gen.generate_sqlalchemy_models(schema),
        "pydantic_code": py_gen.generate_pydantic_schemas(schema),
        "fastapi_code": py_gen.generate_fastapi_endpoints(schema)
    }

    state.add_event("Human Review", "User", "Schema approved and updated by architect.", StepStatus.COMPLETED)
    state.add_event("Artifact Generation", "Generators", "Generated all artifacts from approved schema.", StepStatus.COMPLETED)

    SESSIONS[session_id] = state
    return redirect(url_for("results", session_id=session_id))

@app.route("/results/<session_id>")
def results(session_id):
    state = SESSIONS.get(session_id)
    if not state:
        flash("Session expired or not found. Please re-run.", "warning")
        return redirect(url_for("index"))

    return render_template("results.html", state=state)

@app.route("/sample/<sample_name>")
def sample_demo(sample_name):
    """Instant hackathon demo preset without requiring an uploaded image."""
    session_id = f"demo_{sample_name}_{str(uuid.uuid4())[:4]}"

    sample_schemas = {
        "ecommerce": {
            "database_name": "ecommerce_platform",
            "tables": [
                {
                    "name": "users",
                    "columns": [
                        {"name": "id", "data_type": "BIGINT", "is_primary_key": True, "auto_increment": True, "is_nullable": False},
                        {"name": "username", "data_type": "VARCHAR(50)", "is_unique": True, "is_nullable": False},
                        {"name": "email", "data_type": "VARCHAR(120)", "is_unique": True, "is_nullable": False},
                        {"name": "password_hash", "data_type": "VARCHAR(255)", "is_nullable": False},
                        {"name": "role", "data_type": "VARCHAR(20)", "default_value": "'customer'"}
                    ]
                },
                {
                    "name": "categories",
                    "columns": [
                        {"name": "id", "data_type": "INT", "is_primary_key": True, "auto_increment": True},
                        {"name": "name", "data_type": "VARCHAR(100)", "is_unique": True},
                        {"name": "description", "data_type": "TEXT"}
                    ]
                },
                {
                    "name": "products",
                    "columns": [
                        {"name": "id", "data_type": "BIGINT", "is_primary_key": True, "auto_increment": True},
                        {"name": "category_id", "data_type": "INT", "is_foreign_key": True, "foreign_key_target": "categories.id"},
                        {"name": "name", "data_type": "VARCHAR(150)", "is_nullable": False},
                        {"name": "sku", "data_type": "VARCHAR(64)", "is_unique": True},
                        {"name": "price", "data_type": "DECIMAL(10,2)"},
                        {"name": "stock_quantity", "data_type": "INT", "default_value": "0"}
                    ]
                },
                {
                    "name": "orders",
                    "columns": [
                        {"name": "id", "data_type": "BIGINT", "is_primary_key": True, "auto_increment": True},
                        {"name": "user_id", "data_type": "BIGINT", "is_foreign_key": True, "foreign_key_target": "users.id"},
                        {"name": "order_date", "data_type": "DATETIME", "default_value": "CURRENT_TIMESTAMP"},
                        {"name": "total_amount", "data_type": "DECIMAL(10,2)"},
                        {"name": "status", "data_type": "VARCHAR(30)", "default_value": "'pending'"}
                    ]
                },
                {
                    "name": "order_items",
                    "columns": [
                        {"name": "id", "data_type": "BIGINT", "is_primary_key": True, "auto_increment": True},
                        {"name": "order_id", "data_type": "BIGINT", "is_foreign_key": True, "foreign_key_target": "orders.id"},
                        {"name": "product_id", "data_type": "BIGINT", "is_foreign_key": True, "foreign_key_target": "products.id"},
                        {"name": "quantity", "data_type": "INT", "default_value": "1"},
                        {"name": "unit_price", "data_type": "DECIMAL(10,2)"}
                    ]
                }
            ],
            "relationships": [
                {"source_table": "categories", "target_table": "products", "rel_type": "1:N", "foreign_key": "category_id"},
                {"source_table": "users", "target_table": "orders", "rel_type": "1:N", "foreign_key": "user_id"},
                {"source_table": "orders", "target_table": "order_items", "rel_type": "1:N", "foreign_key": "order_id"},
                {"source_table": "products", "target_table": "order_items", "rel_type": "1:N", "foreign_key": "product_id"}
            ]
        },
        "healthcare": {
            "database_name": "healthcare_ehr",
            "tables": [
                {
                    "name": "patients",
                    "columns": [
                        {"name": "id", "data_type": "BIGINT", "is_primary_key": True, "auto_increment": True},
                        {"name": "first_name", "data_type": "VARCHAR(50)", "is_nullable": False},
                        {"name": "last_name", "data_type": "VARCHAR(50)", "is_nullable": False},
                        {"name": "date_of_birth", "data_type": "DATE"},
                        {"name": "blood_group", "data_type": "VARCHAR(5)"}
                    ]
                },
                {
                    "name": "doctors",
                    "columns": [
                        {"name": "id", "data_type": "BIGINT", "is_primary_key": True, "auto_increment": True},
                        {"name": "name", "data_type": "VARCHAR(100)", "is_nullable": False},
                        {"name": "specialization", "data_type": "VARCHAR(100)"},
                        {"name": "license_number", "data_type": "VARCHAR(50)", "is_unique": True}
                    ]
                },
                {
                    "name": "appointments",
                    "columns": [
                        {"name": "id", "data_type": "BIGINT", "is_primary_key": True, "auto_increment": True},
                        {"name": "patient_id", "data_type": "BIGINT", "is_foreign_key": True, "foreign_key_target": "patients.id"},
                        {"name": "doctor_id", "data_type": "BIGINT", "is_foreign_key": True, "foreign_key_target": "doctors.id"},
                        {"name": "appointment_time", "data_type": "DATETIME"},
                        {"name": "status", "data_type": "VARCHAR(20)", "default_value": "'CONFIRMED'"}
                    ]
                },
                {
                    "name": "medical_records",
                    "columns": [
                        {"name": "id", "data_type": "BIGINT", "is_primary_key": True, "auto_increment": True},
                        {"name": "patient_id", "data_type": "BIGINT", "is_foreign_key": True, "foreign_key_target": "patients.id"},
                        {"name": "diagnosis", "data_type": "TEXT"},
                        {"name": "prescription", "data_type": "TEXT"},
                        {"name": "created_at", "data_type": "TIMESTAMP", "default_value": "CURRENT_TIMESTAMP"}
                    ]
                }
            ],
            "relationships": [
                {"source_table": "patients", "target_table": "appointments", "rel_type": "1:N", "foreign_key": "patient_id"},
                {"source_table": "doctors", "target_table": "appointments", "rel_type": "1:N", "foreign_key": "doctor_id"},
                {"source_table": "patients", "target_table": "medical_records", "rel_type": "1:N", "foreign_key": "patient_id"}
            ]
        },
        "social": {
            "database_name": "social_network",
            "tables": [
                {
                    "name": "users",
                    "columns": [
                        {"name": "id", "data_type": "BIGINT", "is_primary_key": True, "auto_increment": True},
                        {"name": "username", "data_type": "VARCHAR(50)", "is_unique": True},
                        {"name": "bio", "data_type": "TEXT"}
                    ]
                },
                {
                    "name": "posts",
                    "columns": [
                        {"name": "id", "data_type": "BIGINT", "is_primary_key": True, "auto_increment": True},
                        {"name": "user_id", "data_type": "BIGINT", "is_foreign_key": True, "foreign_key_target": "users.id"},
                        {"name": "content", "data_type": "TEXT"},
                        {"name": "created_at", "data_type": "TIMESTAMP", "default_value": "CURRENT_TIMESTAMP"}
                    ]
                },
                {
                    "name": "comments",
                    "columns": [
                        {"name": "id", "data_type": "BIGINT", "is_primary_key": True, "auto_increment": True},
                        {"name": "post_id", "data_type": "BIGINT", "is_foreign_key": True, "foreign_key_target": "posts.id"},
                        {"name": "user_id", "data_type": "BIGINT", "is_foreign_key": True, "foreign_key_target": "users.id"},
                        {"name": "comment_text", "data_type": "VARCHAR(500)"}
                    ]
                }
            ],
            "relationships": [
                {"source_table": "users", "target_table": "posts", "rel_type": "1:N", "foreign_key": "user_id"},
                {"source_table": "posts", "target_table": "comments", "rel_type": "1:N", "foreign_key": "post_id"},
                {"source_table": "users", "target_table": "comments", "rel_type": "1:N", "foreign_key": "user_id"}
            ]
        }
    }

    raw_data = sample_schemas.get(sample_name, sample_schemas["ecommerce"])
    schema = orchestrator.schema_agent.normalize_schema(raw_data)

    from core.workflow import WorkflowState, StepStatus
    state = WorkflowState(session_id=session_id)
    state.database_schema = schema.model_dump()

    val_result = orchestrator.validation_agent.validate(schema)
    state.validation_result = val_result.model_dump()

    uml_model = orchestrator.uml_agent.generate_uml_model(schema)

    erd_gen = ERDGenerator()
    uml_gen = UMLGenerator()
    mysql_gen = MySQLGenerator()
    py_gen = PythonGenerator()

    state.generated_artifacts = {
        "erd_mermaid": erd_gen.generate_mermaid_erd(schema),
        "erd_dot": erd_gen.generate_graphviz(schema),
        "uml_mermaid": uml_gen.generate_mermaid_class_diagram(uml_model),
        "uml_plantuml": uml_gen.generate_plantuml(uml_model),
        "uml_sequence": uml_gen.generate_sequence_diagram(uml_model),
        "mysql_sql": mysql_gen.generate_sql(schema),
        "sqlalchemy_code": py_gen.generate_sqlalchemy_models(schema),
        "pydantic_code": py_gen.generate_pydantic_schemas(schema),
        "fastapi_code": py_gen.generate_fastapi_endpoints(schema)
    }

    state.add_event("Preset Loader", "System", f"Loaded preset template '{sample_name}'.", StepStatus.COMPLETED)
    state.add_event("Artifact Generation", "Generators", "Generated all artifacts successfully.", StepStatus.COMPLETED)

    SESSIONS[session_id] = state
    return redirect(url_for("results", session_id=session_id))

@app.route("/download/file/<session_id>/<artifact_key>")
def download_file(session_id, artifact_key):
    state = SESSIONS.get(session_id)
    if not state:
        flash("File session expired.", "warning")
        return redirect(url_for("index"))

    content = state.generated_artifacts.get(artifact_key, "")
    ext_map = {
        "erd_mermaid": "mmd",
        "erd_dot": "dot",
        "uml_mermaid": "mmd",
        "uml_plantuml": "puml",
        "mysql_sql": "sql",
        "sqlalchemy_code": "py",
        "pydantic_code": "py",
        "fastapi_code": "py"
    }
    ext = ext_map.get(artifact_key, "txt")
    filename = f"{session_id}_{artifact_key}.{ext}"

    mem = io.BytesIO(content.encode("utf-8"))
    return send_file(mem, as_attachment=True, download_name=filename, mimetype="text/plain")

@app.route("/download/bundle/<session_id>")
def download_bundle(session_id):
    """Packages all generated outputs into a single zip archive for download."""
    state = SESSIONS.get(session_id)
    if not state:
        flash("Session expired.", "warning")
        return redirect(url_for("index"))

    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. SQL
        zf.writestr(f"sql/schema.sql", state.generated_artifacts.get("mysql_sql", ""))
        # 2. Python ORM
        zf.writestr(f"python/models.py", state.generated_artifacts.get("sqlalchemy_code", ""))
        zf.writestr(f"python/schemas.py", state.generated_artifacts.get("pydantic_code", ""))
        zf.writestr(f"python/api_routes.py", state.generated_artifacts.get("fastapi_code", ""))
        # 3. Diagrams
        zf.writestr(f"diagrams/erd.mmd", state.generated_artifacts.get("erd_mermaid", ""))
        zf.writestr(f"diagrams/erd.dot", state.generated_artifacts.get("erd_dot", ""))
        zf.writestr(f"diagrams/uml_class.mmd", state.generated_artifacts.get("uml_mermaid", ""))
        zf.writestr(f"diagrams/uml_class.puml", state.generated_artifacts.get("uml_plantuml", ""))
        zf.writestr(f"diagrams/sequence.mmd", state.generated_artifacts.get("uml_sequence", ""))
        # 4. JSON Schema spec
        zf.writestr(f"schema.json", json.dumps(state.database_schema, indent=2))

    mem_zip.seek(0)
    return send_file(
        mem_zip,
        as_attachment=True,
        download_name=f"SchemaMindAI_Export_{session_id}.zip",
        mimetype="application/zip"
    )

@app.route("/api/health")
def api_health():
    health = gemma_client.check_health()
    return jsonify(health)

if __name__ == "__main__":
    logger.info(f"Starting SchemaMindAI on http://{Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
