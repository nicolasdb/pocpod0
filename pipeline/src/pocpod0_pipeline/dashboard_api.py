"""ACL Enforcement Dashboard API for Story 6.3.

FastAPI backend that queries CSS pod ACL state live and demonstrates
"private by default" enforcement. Routes grant/revoke through acl-manage skill,
displays troll attack results live.
"""

import os
import httpx
import json
import subprocess
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, status
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

# acl-manage handler constants
ALL_PODS = "ayoub,claire-student-1,claire-student-2,fatima-child-1,fatima-child-2,school-community"
HANDLER_PATH = REPO_ROOT / "agents" / "skills" / "acl-manage" / "handler.py"

# Troll attack constants
TROLL_PATH = REPO_ROOT / "agents" / "troll-adversary" / "attacks" / "run_comprehensive.py"
TROLL_JSONL_PATH = REPO_ROOT / "data" / "troll-run.jsonl"
BLOCKING_CATEGORIES = {"acl_enforcement", "sparql_injection"}


def call_acl_manage(action: str, pod: str, webid: str | None = None, actor: str | None = None) -> tuple[bool, str]:
    """Call acl-manage handler.py subprocess and return (ok, message)."""
    cmd = [
        "python", str(HANDLER_PATH),
        "--action", action,
        "--pod-name", pod,
    ]
    if webid:
        cmd += ["--identity", webid]
    if actor:
        cmd += ["--role", actor, "--access-level", "read"]

    env = {
        **os.environ,
        "CSS_CONNECT_URL": "http://localhost:3000",
        "AGENT_POD_OWNERSHIP": ALL_PODS,
        "AGENT_ID": "dashboard",
    }

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)

        # Parse JSON response
        try:
            response = json.loads(result.stdout)
            if result.returncode == 0 and response.get("status") == "ok":
                return (True, response.get("message", "Success"))
            else:
                # Handler returned error (exit code 1) or status != "ok"
                return (False, response.get("message", "Handler error"))
        except json.JSONDecodeError:
            return (False, result.stderr or "No JSON response from handler")
    except subprocess.TimeoutExpired:
        return (False, "acl-manage handler timeout")
    except Exception as e:
        return (False, f"Error calling acl-manage: {str(e)}")


def parse_troll_results() -> dict:
    """Parse troll-run.jsonl and return categorized summary.

    Returns:
        {
            "categories": {
                "acl_enforcement": {"blocking": True, "passed": X, "partial": Y, "failed": Z, "total": T},
                ...
            },
            "run_summary": {"total_tests": X, "total_passed": Y, ...} or None
        }
    """
    categories = {}
    run_summary = None

    if not TROLL_JSONL_PATH.exists():
        return {"categories": categories, "run_summary": run_summary}

    try:
        with open(TROLL_JSONL_PATH, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    event_type = event.get("event_type")

                    if event_type == "troll.category.done":
                        category = event.get("attack_category")
                        categories[category] = {
                            "blocking": event.get("blocking", False),
                            "passed": event.get("passed", 0),
                            "partial": event.get("partial", 0),
                            "failed": event.get("failed", 0),
                            "total": event.get("total", 0),
                        }
                    elif event_type == "troll.run.done":
                        run_summary = {
                            "total_tests": event.get("total_tests", 0),
                            "total_passed": event.get("total_passed", 0),
                            "total_partial": event.get("total_partial", 0),
                            "total_failed": event.get("total_failed", 0),
                            "blocking_pass": event.get("blocking_pass", False),
                        }
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        pass

    return {"categories": categories, "run_summary": run_summary}


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


class TrollResultsResponse(BaseModel):
    categories: dict
    run_summary: Optional[dict] = None


class TrollCategory(BaseModel):
    name: str
    blocking: bool
    passed: int
    partial: int
    failed: int
    total: int


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
    """Grant ACL access to a pod for an actor via acl-manage skill."""
    if pod not in REAL_PODS:
        raise HTTPException(status_code=400, detail=f"Unknown pod: {pod}")

    if req.actor not in ACTOR_WEBIDS:
        raise HTTPException(status_code=400, detail=f"Unknown actor: {req.actor}")

    agent_webid = ACTOR_WEBIDS[req.actor]
    ok, msg = call_acl_manage(
        action="grant",
        pod=pod,
        webid=agent_webid,
        actor=req.actor
    )

    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"ok": True, "message": msg}


# Revoke endpoint
@app.post("/api/pods/{pod}/revoke")
async def revoke_access(pod: str, req: RevokeRequest):
    """Revoke ACL access from a pod for an actor via acl-manage skill."""
    if pod not in REAL_PODS:
        raise HTTPException(status_code=400, detail=f"Unknown pod: {pod}")

    if req.actor not in ACTOR_WEBIDS:
        raise HTTPException(status_code=400, detail=f"Unknown actor: {req.actor}")

    agent_webid = ACTOR_WEBIDS[req.actor]
    ok, msg = call_acl_manage(
        action="revoke",
        pod=pod,
        webid=agent_webid
    )

    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"ok": True, "message": msg}


# Troll run endpoint - triggers comprehensive attack suite
@app.post("/api/troll/run", status_code=status.HTTP_202_ACCEPTED)
async def run_troll():
    """Trigger troll comprehensive attack suite (runs in background)."""
    env = {
        **os.environ,
        "CSS_BASE_URL": CSS_BASE_URL,
        # Also include other required env vars for troll
    }

    try:
        # Run troll in background (don't wait for completion)
        subprocess.Popen(
            ["python", str(TROLL_PATH)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"status": "accepted", "message": "Troll comprehensive run started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start troll: {str(e)}")


# Troll results endpoint - get latest test results
@app.get("/api/troll/results")
async def get_troll_results() -> TrollResultsResponse:
    """Get latest troll attack results from troll-run.jsonl."""
    results = parse_troll_results()
    return TrollResultsResponse(
        categories=results["categories"],
        run_summary=results["run_summary"]
    )


# Mount static files (AFTER all /api/* routes so they take precedence)
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def main():
    """Entry point for uvicorn."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
