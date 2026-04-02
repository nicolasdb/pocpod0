"""ACL Enforcement Dashboard API for Story 6.2.

FastAPI backend that queries CSS pod ACL state live and demonstrates
"private by default" enforcement. Queries CSS directly via PodProvisioner.
"""

import os
import httpx
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pocpod0_pipeline.provision_pods import PodProvisioner


# Configuration
REPO_ROOT = Path(__file__).parent.parent.parent.parent
CSS_BASE_URL = os.environ.get("CSS_BASE_URL", "http://localhost:3000")
POD_CONFIG_PATH = REPO_ROOT / "infra" / "css" / "pods" / "pod-config.yaml"
STATIC_DIR = REPO_ROOT / "dashboard" / "static"

# Actor WebIDs (from pod-config.yaml)
ACTOR_WEBIDS = {
    "ayoub": "http://localhost:3000/ayoub/profile/card#me",
    "claire": "http://localhost:3000/claire/profile/card#me",
    "fatima": "http://localhost:3000/fatima/profile/card#me",
    "marc": "http://localhost:3000/marc/profile/card#me",
    "isabelle": "http://localhost:3000/isabelle/profile/card#me",
    "troll": "http://localhost:3000/troll/profile/card#me",
}

# Display names for pods
DISPLAY_NAMES = {
    "ayoub": "Ayoub",
    "claire-student-1": "Alex (Claire's class)",
    "claire-student-2": "Jordan (Claire's class)",
    "fatima-child-1": "Sam (Fatima's family, NL school)",
    "fatima-child-2": "Léa (Fatima's family, FR school)",
    "school-community": "School Community",
}

# Real pods (6 only)
REAL_PODS = [
    "ayoub",
    "claire-student-1",
    "claire-student-2",
    "fatima-child-1",
    "fatima-child-2",
    "school-community",
]

# Initialize FastAPI app
app = FastAPI(title="POCpod0 ACL Dashboard API")

# Initialize PodProvisioner singleton
_provisioner = PodProvisioner(
    css_base_url=CSS_BASE_URL,
    config_path=str(POD_CONFIG_PATH),
)


# Request/Response models
class ProbeRequest(BaseModel):
    as_actor: Optional[str] = None


class ProbeResponse(BaseModel):
    pod: str
    as_actor: str
    status_code: int
    allowed: bool
    error: Optional[str] = None


class GrantRequest(BaseModel):
    actor: str
    access_level: str = "read"


class RevokeRequest(BaseModel):
    actor: str


class HealthResponse(BaseModel):
    css: bool
    oxigraph: bool
    qdrant: bool


class PodAclGrant(BaseModel):
    actor_label: str
    webid: str
    modes: list


class PodCardResponse(BaseModel):
    pod: str
    display_name: str
    grants: list
    is_private: bool


# Health check endpoint
@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Check service health (CSS, Oxigraph, Qdrant)."""
    css_ok = False
    oxigraph_ok = False
    qdrant_ok = False

    async with httpx.AsyncClient(timeout=3.0) as client:
        # Check CSS by querying a known pod (avoids identifier space validation on root)
        try:
            resp = await client.get(f"{CSS_BASE_URL}/ayoub/", follow_redirects=True)
            css_ok = resp.status_code < 500
        except httpx.RequestError:
            pass

        # Check Oxigraph (default port :7878)
        try:
            resp = await client.get("http://localhost:7878/", follow_redirects=True)
            oxigraph_ok = resp.status_code < 500
        except httpx.RequestError:
            pass

        # Check Qdrant (default port :6333)
        try:
            resp = await client.get("http://localhost:6333/", follow_redirects=True)
            qdrant_ok = resp.status_code < 500
        except httpx.RequestError:
            pass

    return HealthResponse(css=css_ok, oxigraph=oxigraph_ok, qdrant=qdrant_ok)


# Get all pods with ACL state
@app.get("/api/pods", response_model=list)
async def get_pods():
    """Get list of all real pods with ACL state."""
    pods = []

    for pod_name in REAL_PODS:
        ok, result = _provisioner.view_acl_state(pod_name)

        # Build grant list — exclude self (pod owner) and provisioner system grants
        HIDDEN_ACTORS = {pod_name, "provisioner"}
        grants = []
        if ok and "acl_grants" in result:
            for grant in result["acl_grants"]:
                label = grant.get("agent", "")
                if label not in HIDDEN_ACTORS:
                    grants.append({
                        "actor_label": label,
                        "webid": grant.get("agent_webid", ""),
                        "modes": grant.get("access_modes", [])
                    })

        # Pod is private if no external grants (owner/provisioner don't count)
        is_private = len(grants) == 0

        pods.append({
            "pod": pod_name,
            "display_name": DISPLAY_NAMES.get(pod_name, pod_name),
            "grants": grants,
            "is_private": is_private
        })

    return pods


# Probe endpoint - test access without/with auth
@app.post("/api/pods/{pod}/probe", response_model=ProbeResponse)
async def probe_pod(pod: str, req: ProbeRequest):
    """Probe pod access (unauthenticated or as specified actor)."""
    if pod not in REAL_PODS:
        raise HTTPException(status_code=400, detail=f"Unknown pod: {pod}")

    url = f"{CSS_BASE_URL}/{pod}/"
    headers = {}
    as_actor = req.as_actor or "anonymous"

    # Add auth header if actor specified
    if req.as_actor and req.as_actor in ACTOR_WEBIDS:
        headers["Authorization"] = f"WebID {ACTOR_WEBIDS[req.as_actor]}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            return ProbeResponse(
                pod=pod,
                as_actor=as_actor,
                status_code=resp.status_code,
                allowed=resp.status_code == 200
            )
    except httpx.RequestError as e:
        return ProbeResponse(
            pod=pod,
            as_actor=as_actor,
            status_code=0,
            allowed=False,
            error=str(e)
        )


# Grant endpoint
@app.post("/api/pods/{pod}/grant")
async def grant_access(pod: str, req: GrantRequest):
    """Grant ACL access to a pod for an actor."""
    if pod not in REAL_PODS:
        raise HTTPException(status_code=400, detail=f"Unknown pod: {pod}")

    if req.actor not in ACTOR_WEBIDS:
        raise HTTPException(status_code=400, detail=f"Unknown actor: {req.actor}")

    agent_webid = ACTOR_WEBIDS[req.actor]
    ok, msg = _provisioner.grant_acl_access(
        pod_name=pod,
        agent_webid=agent_webid,
        role=req.actor,
        access_level=req.access_level
    )

    if not ok:
        raise HTTPException(status_code=500, detail=msg)

    return {"ok": True, "message": msg}


# Revoke endpoint
@app.post("/api/pods/{pod}/revoke")
async def revoke_access(pod: str, req: RevokeRequest):
    """Revoke ACL access from a pod for an actor."""
    if pod not in REAL_PODS:
        raise HTTPException(status_code=400, detail=f"Unknown pod: {pod}")

    if req.actor not in ACTOR_WEBIDS:
        raise HTTPException(status_code=400, detail=f"Unknown actor: {req.actor}")

    agent_webid = ACTOR_WEBIDS[req.actor]
    ok, msg = _provisioner.revoke_acl_access(
        pod_name=pod,
        agent_webid=agent_webid
    )

    if not ok:
        raise HTTPException(status_code=500, detail=msg)

    return {"ok": True, "message": msg}


# Mount static files (AFTER all /api/* routes so they take precedence)
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def main():
    """Entry point for uvicorn."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
