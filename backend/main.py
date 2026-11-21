import os

from sqlalchemy import URL, create_engine, text
from sqlalchemy import URL, create_engine, select, text

from backend.models.category import Category
from fastapi import FastAPI

from backend.routes.auth import AuthRoutes

from backend.routes.complaint import create_complaints_router

from backend.routes.staff_workflow import create_staff_workflow_router

from backend.routes.comments import create_comments_router

from backend.routes.notifications import create_notifications_router

from backend.routes.reopen_requests import create_reopen_router

from backend.routes.admin_insights import create_admin_insights_router

app = FastAPI(
    title="CampusFix API",
    description="Backend API for CampusFix",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "Welcome to CampusFix API",
        "status": "running"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "application": "CampusFix"
    }
db_url = URL.create(
    "postgresql+psycopg",
    username="campusfix_app",
    password=os.environ["CAMPUSFIX_DB_PASSWORD"],
    host="127.0.0.1",
    port=5432,
    database="campusfix",
)
engine = create_engine(db_url)


@app.get("/api/health/db")
def database_health():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar_one()

    return {"database": "connected", "result": result}
@app.get("/api/categories")
def list_categories():
    table = Category.__table__
    query = select(table.c.id, table.c.name).order_by(table.c.id)

    with engine.connect() as connection:
        rows = connection.execute(query).all()

    return [{"id": category_id, "name": name} for category_id, name in rows]
auth = AuthRoutes(engine)
app.include_router(auth.router)
app.include_router(create_complaints_router(engine, auth.current_user))
app.include_router(
    create_staff_workflow_router(engine, auth.current_user)
)
app.include_router(create_comments_router(engine, auth.current_user))
app.include_router(
    create_notifications_router(engine, auth.current_user)
)
app.include_router(
    create_reopen_router(engine, auth.current_user)
)
app.include_router(
    create_admin_insights_router(engine, auth.current_user)
)