import pytest
from core.schema_models import DatabaseSchema, TableSchema, ColumnSchema, ForeignKeyConstraint
from generators.erd_generator import ERDGenerator
from generators.uml_generator import UMLGenerator
from generators.python_generator import PythonGenerator
from agents.uml_agent import UMLAgent
from core.gemma_client import GemmaClient

def build_sample_schema():
    users_tbl = TableSchema(
        name="users",
        columns=[
            ColumnSchema(name="id", data_type="BIGINT", is_primary_key=True),
            ColumnSchema(name="username", data_type="VARCHAR(50)", is_unique=True),
            ColumnSchema(name="email", data_type="VARCHAR(120)")
        ],
        primary_keys=["id"]
    )
    products_tbl = TableSchema(
        name="products",
        columns=[
            ColumnSchema(name="id", data_type="BIGINT", is_primary_key=True),
            ColumnSchema(name="title", data_type="VARCHAR(200)"),
            ColumnSchema(name="price", data_type="DECIMAL(10,2)")
        ],
        primary_keys=["id"]
    )
    return DatabaseSchema(database_name="app_db", tables=[users_tbl, products_tbl])

def test_erd_generator():
    schema = build_sample_schema()
    gen = ERDGenerator()
    mermaid_erd = gen.generate_mermaid_erd(schema)
    assert "erDiagram" in mermaid_erd
    assert "USERS {" in mermaid_erd
    assert "PRODUCTS {" in mermaid_erd

    dot_erd = gen.generate_graphviz(schema)
    assert "digraph ERD" in dot_erd
    assert '"users"' in dot_erd

def test_uml_generator():
    schema = build_sample_schema()
    uml_agent = UMLAgent(GemmaClient(provider="mock"))
    uml_model = uml_agent.generate_uml_model(schema)

    gen = UMLGenerator()
    class_diagram = gen.generate_mermaid_class_diagram(uml_model)
    assert "classDiagram" in class_diagram
    assert "class User {" in class_diagram
    assert "class Product {" in class_diagram

    plantuml = gen.generate_plantuml(uml_model)
    assert "@startuml" in plantuml
    assert "@enduml" in plantuml

    sequence = gen.generate_sequence_diagram(uml_model)
    assert "sequenceDiagram" in sequence

def test_python_generator():
    schema = build_sample_schema()
    gen = PythonGenerator()

    # SQLAlchemy
    sa_code = gen.generate_sqlalchemy_models(schema)
    assert "class User(Base):" in sa_code
    assert 'mapped_column' in sa_code

    # Pydantic
    pydantic_code = gen.generate_pydantic_schemas(schema)
    assert "class UserBase(BaseModel):" in pydantic_code
    assert "class UserResponse(UserBase):" in pydantic_code

    # FastAPI
    api_code = gen.generate_fastapi_endpoints(schema)
    assert "@router.get('/users'" in api_code
