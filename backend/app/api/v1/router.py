from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.github import router as github_router
from app.api.v1.endpoints.repositories import router as repositories_router
from app.api.v1.endpoints.analysis import router as analysis_router
from app.api.v1.endpoints.agent import router as agent_router
from app.api.v1.endpoints.jobs import router as jobs_router
from app.api.v1.endpoints.agent_runs import router as agent_runs_router
from app.api.v1.endpoints.audit import router as audit_router
from app.api.v1.endpoints.system import router as system_router
from app.api.v1.endpoints.governance import router as governance_router
from app.api.v1.endpoints.organizations import router as organizations_router
from app.api.v1.endpoints.org_audit import router as org_audit_router
from app.api.v1.endpoints.webhooks import router as webhooks_router
from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.recovery import router as recovery_router

router = APIRouter()




# Register versioned authentication endpoints
router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Register versioned GitHub endpoints
router.include_router(github_router, prefix="/github", tags=["GitHub"])

# Register versioned repository management endpoints
router.include_router(repositories_router, prefix="/repositories", tags=["Repositories"])

# Register versioned repository intelligence/analysis endpoints
router.include_router(analysis_router, prefix="/repositories", tags=["Analysis"])

# Register versioned agent endpoints
router.include_router(agent_router, prefix="", tags=["Agent"])

# Register versioned job management & monitoring endpoints
router.include_router(jobs_router, prefix="", tags=["Jobs"])

# Register versioned multi-agent run endpoints
router.include_router(agent_runs_router, prefix="", tags=["Multi-Agent Runs"])

# Register versioned audit endpoints
router.include_router(audit_router, prefix="/audit", tags=["Audit Log"])

# Register versioned system monitoring endpoints
router.include_router(system_router, prefix="/system", tags=["System Monitoring"])

# Register versioned governance endpoints
router.include_router(governance_router, prefix="/governance", tags=["Governance"])

# Register organization endpoints
router.include_router(organizations_router, prefix="/organizations", tags=["Organizations"])
router.include_router(org_audit_router, prefix="/organizations", tags=["Organization Audit"])
router.include_router(webhooks_router, prefix="", tags=["Webhooks & Events"])
router.include_router(analytics_router, prefix="", tags=["Analytics & Usage"])
router.include_router(recovery_router, prefix="/recovery", tags=["Disaster Recovery"])




# Version 1 root check
@router.get("/info", tags=["System"])
async def get_v1_info():
    """Returns metadata about version 1 api endpoints."""
    return {
        "version": "v1",
        "name": "CodeForge AI Core API",
        "description": "API endpoints for CodeForge AI software engineering agent operations."
    }
