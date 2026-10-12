import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from app.api.app.router import router as app_router
from app.api.internal.router import router as internal_router
from app.config import settings
from app.exceptions import APIException


def route_operation_id(route: APIRoute) -> str:
    # Use the endpoint function name as the operationId instead of FastAPI's
    # default "{name}_{path}_{method}". This keeps the generated frontend client
    # readable (e.g. useGetCurrentUser instead of useGetCurrentUserUsersMeGet).
    # Endpoint function names within each sub-app are unique, so no collisions.
    return route.name


# The OpenAPI schema and the interactive docs it powers expose the full API
# surface, so they are served everywhere except production. Passed to every app
# below: the mounted sub-apps serve their own docs, independently of the root.
openapi_url = None if settings.is_production else "/openapi.json"
docs_url = None if settings.is_production else "/docs"
redoc_url = None if settings.is_production else "/redoc"

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=openapi_url,
    docs_url=docs_url,
    redoc_url=redoc_url,
)

app_api = FastAPI(
    title="PlanStride App API",
    contact={"name": "PlanStride"},
    description=(
        "The customer API. Every resource is scoped to an organization the "
        "caller belongs to: /organizations/{organization_id}/..."
    ),
    generate_unique_id_function=route_operation_id,
    openapi_tags=[
        {"name": "meta", "description": "Health and service metadata"},
        {"name": "auth", "description": "Sign-up, sign-in and session"},
        {"name": "users", "description": "The signed-in user"},
        {"name": "organizations", "description": "The caller's organizations"},
        {"name": "members", "description": "Organization members and roles"},
        {"name": "invitations", "description": "Invite links into an organization"},
        {"name": "teams", "description": "Teams, their leads and the team's week"},
        {"name": "plans", "description": "Weekly plans and their tasks"},
        {"name": "reviews", "description": "Approving and returning plans"},
        {"name": "ai", "description": "AI plan review and drafting"},
    ],
    openapi_url=openapi_url,
    docs_url=docs_url,
    redoc_url=redoc_url,
)


@app_api.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    return exc.to_response()


app_api.include_router(app_router)
app_api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/app", app_api, "app")


internal_api = FastAPI(
    title="PlanStride Internal API",
    contact={"name": "PlanStride"},
    description=(
        "The back office for PlanStride's own staff (is_platform_staff). "
        "Customer roles grant nothing here, and no endpoint returns plan content."
    ),
    generate_unique_id_function=route_operation_id,
    openapi_tags=[
        {"name": "meta", "description": "Health and service metadata"},
        {"name": "auth", "description": "Staff sign-in and session"},
        {"name": "overview", "description": "Headline numbers"},
        {"name": "users", "description": "Accounts across all organizations"},
        {"name": "organizations", "description": "Customer organizations"},
        {"name": "ai-usage", "description": "AI calls, failures and rate limits"},
    ],
    openapi_url=openapi_url,
    docs_url=docs_url,
    redoc_url=redoc_url,
)


@internal_api.exception_handler(APIException)
async def internal_api_exception_handler(request: Request, exc: APIException):
    return exc.to_response()


internal_api.include_router(internal_router)
internal_api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/internal", internal_api, "internal")


obj_dir = os.path.join(os.getcwd(), "obj")
if os.path.exists(obj_dir):
    app.mount("/obj", StaticFiles(directory="obj"), name="obj")
