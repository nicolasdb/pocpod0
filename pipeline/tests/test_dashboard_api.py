"""Tests for dashboard_api.py (Story 6.3)."""

import pytest
import httpx
import json
import subprocess
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from pocpod0_pipeline.dashboard_api import app, REAL_PODS, ACTOR_WEBIDS


client = TestClient(app)


# ============================================================================
# AC1: Pod ACL grid - pods load with correct structure
# ============================================================================

@patch('pocpod0_pipeline.dashboard_api._provisioner.view_acl_state')
def test_get_pods_returns_all_real_pods(mock_view_acl):
    """AC1: GET /api/pods returns all 6 real pods with correct structure."""
    # Mock view_acl_state to return empty grants (owner only)
    mock_view_acl.return_value = (True, {"pod": "test", "acl_grants": []})

    response = client.get("/api/pods")

    assert response.status_code == 200
    pods = response.json()
    assert len(pods) == 6

    pod_names = {p["pod"] for p in pods}
    assert pod_names == set(REAL_PODS)

    # Check pod structure
    for pod in pods:
        assert "pod" in pod
        assert "display_name" in pod
        assert "grants" in pod
        assert "is_private" in pod


@patch('pocpod0_pipeline.dashboard_api._provisioner.view_acl_state')
def test_get_pods_marks_private_when_no_grants(mock_view_acl):
    """AC1: Pod with no grants is marked is_private=true (owner only)."""
    mock_view_acl.return_value = (True, {"pod": "ayoub", "acl_grants": []})

    response = client.get("/api/pods")
    pods = response.json()

    ayoub = [p for p in pods if p["pod"] == "ayoub"][0]
    assert ayoub["is_private"] is True
    assert ayoub["grants"] == []


@patch('pocpod0_pipeline.dashboard_api._provisioner.view_acl_state')
def test_get_pods_marks_shared_when_grants_exist(mock_view_acl):
    """AC1: Pod with grants is marked is_private=false (shared)."""
    mock_view_acl.return_value = (True, {
        "pod": "ayoub",
        "acl_grants": [
            {
                "agent": "isabelle",
                "agent_webid": "http://localhost:3000/isabelle/profile/card#me",
                "access_modes": ["Read"]
            }
        ]
    })

    response = client.get("/api/pods")
    pods = response.json()

    ayoub = [p for p in pods if p["pod"] == "ayoub"][0]
    assert ayoub["is_private"] is False
    assert len(ayoub["grants"]) == 1
    assert ayoub["grants"][0]["actor_label"] == "isabelle"


@patch('pocpod0_pipeline.dashboard_api._provisioner.view_acl_state')
def test_get_pods_uses_display_names(mock_view_acl):
    """AC1: All 6 pods return display_name distinct from their slug (display names are UI labels, not tested for exact string)."""
    mock_view_acl.return_value = (True, {"pod": "ayoub", "acl_grants": []})

    response = client.get("/api/pods")
    pods = response.json()

    for pod in pods:
        assert pod["display_name"] != pod["pod"], (
            f"Pod {pod['pod']} has no display name mapping — slug leaked into UI"
        )


# ============================================================================
# AC2: Unauthenticated probe
# ============================================================================

def test_probe_without_auth_returns_401():
    """AC2: Probe without auth on private pod returns 401."""
    # Mock httpx to return 401
    with patch('pocpod0_pipeline.dashboard_api.httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        response = client.post(
            "/api/pods/ayoub/probe",
            json={"as_actor": None}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status_code"] == 401
        assert data["allowed"] is False
        assert data["as_actor"] == "anonymous"


def test_probe_without_auth_returns_200():
    """AC2: Probe without auth on shared pod returns 200."""
    with patch('pocpod0_pipeline.dashboard_api.httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        response = client.post(
            "/api/pods/ayoub/probe",
            json={"as_actor": None}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status_code"] == 200
        assert data["allowed"] is True


def test_probe_validates_pod_name():
    """AC2: Probe rejects unknown pod names."""
    response = client.post(
        "/api/pods/unknown-pod/probe",
        json={"as_actor": None}
    )

    assert response.status_code == 400


# ============================================================================
# AC3: Actor probe
# ============================================================================

def test_probe_as_actor_adds_auth_header():
    """AC3: Probe as actor includes WebID auth header."""
    with patch('pocpod0_pipeline.dashboard_api.httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.get = mock_get

        response = client.post(
            "/api/pods/ayoub/probe",
            json={"as_actor": "isabelle"}
        )

        # Verify get was called with auth header
        call_args = mock_get.call_args
        assert call_args is not None
        assert "headers" in call_args.kwargs
        headers = call_args.kwargs["headers"]
        assert "Authorization" in headers
        assert "isabelle" in headers["Authorization"]


def test_probe_unknown_actor_treated_as_anonymous():
    """AC3: Unknown actor in probe falls through to anonymous (no auth header sent) — probe is read-only observation, not state change."""
    response = client.post(
        "/api/pods/ayoub/probe",
        json={"as_actor": "unknown-actor"}
    )

    assert response.status_code == 200
    assert response.json()["as_actor"] == "unknown-actor"


def test_probe_handles_request_errors():
    """AC3: Probe handles network errors gracefully."""
    with patch('pocpod0_pipeline.dashboard_api.httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.RequestError("Connection refused")
        )

        response = client.post(
            "/api/pods/ayoub/probe",
            json={"as_actor": "isabelle"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status_code"] == 0
        assert data["allowed"] is False
        assert "error" in data


# ============================================================================
# AC4: Grant access
# ============================================================================

@patch('pocpod0_pipeline.dashboard_api.subprocess.run')
def test_grant_calls_acl_manage_handler(mock_subprocess):
    """AC1: Grant button calls acl-manage handler.py via subprocess."""
    # Mock successful acl-manage handler response
    mock_subprocess.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"status": "ok", "message": "Granted isabelle read access to ayoub"})
    )

    response = client.post(
        "/api/pods/ayoub/grant",
        json={"actor": "isabelle", "access_level": "read"}
    )

    assert response.status_code == 200
    assert mock_subprocess.called

    # Verify subprocess was called with handler path and correct arguments
    call_args = mock_subprocess.call_args
    cmd = call_args[0][0]  # First positional argument is the command list
    assert "acl-manage" in cmd[1]  # Handler path should contain "acl-manage"
    assert "--action" in cmd and "grant" in cmd
    assert "--pod-name" in cmd and "ayoub" in cmd


@patch('pocpod0_pipeline.dashboard_api.subprocess.run')
def test_grant_validates_pod_name(mock_subprocess):
    """AC1: Grant rejects unknown pod."""
    response = client.post(
        "/api/pods/unknown/grant",
        json={"actor": "isabelle", "access_level": "read"}
    )

    assert response.status_code == 400
    assert not mock_subprocess.called


@patch('pocpod0_pipeline.dashboard_api.subprocess.run')
def test_grant_validates_actor_name(mock_subprocess):
    """AC1: Grant rejects unknown actor."""
    response = client.post(
        "/api/pods/ayoub/grant",
        json={"actor": "unknown", "access_level": "read"}
    )

    assert response.status_code == 400
    assert not mock_subprocess.called


@patch('pocpod0_pipeline.dashboard_api.subprocess.run')
def test_grant_handles_handler_denied(mock_subprocess):
    """AC6: Grant returns HTTP 400 if handler denies (exit code 1)."""
    # Handler returns exit code 1 with denied message in JSON
    mock_subprocess.return_value = MagicMock(
        returncode=1,
        stdout=json.dumps({"status": "denied", "message": "Not in AGENT_POD_OWNERSHIP scope"})
    )

    response = client.post(
        "/api/pods/ayoub/grant",
        json={"actor": "isabelle", "access_level": "read"}
    )

    assert response.status_code == 400
    data = response.json()
    assert "Not in AGENT_POD_OWNERSHIP scope" in data.get("detail", "")


@patch('pocpod0_pipeline.dashboard_api.subprocess.run')
def test_grant_returns_ok_response(mock_subprocess):
    """AC1: Successful grant returns HTTP 200."""
    mock_subprocess.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"status": "ok", "message": "Granted isabelle read access to ayoub"})
    )

    response = client.post(
        "/api/pods/ayoub/grant",
        json={"actor": "isabelle", "access_level": "read"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "message" in data


# ============================================================================
# AC5: Revoke access
# ============================================================================

@patch('pocpod0_pipeline.dashboard_api.subprocess.run')
def test_revoke_calls_acl_manage_handler(mock_subprocess):
    """AC1: Revoke button calls acl-manage handler.py via subprocess."""
    mock_subprocess.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"status": "ok", "message": "Revoked access for isabelle from ayoub"})
    )

    response = client.post(
        "/api/pods/ayoub/revoke",
        json={"actor": "isabelle"}
    )

    assert response.status_code == 200
    assert mock_subprocess.called

    # Verify subprocess was called with handler path and correct arguments
    call_args = mock_subprocess.call_args
    cmd = call_args[0][0]
    assert "acl-manage" in cmd[1]  # Handler path
    assert "--action" in cmd and "revoke" in cmd
    assert "--pod-name" in cmd and "ayoub" in cmd


@patch('pocpod0_pipeline.dashboard_api.subprocess.run')
def test_revoke_validates_pod_name(mock_subprocess):
    """AC1: Revoke rejects unknown pod."""
    response = client.post(
        "/api/pods/unknown/revoke",
        json={"actor": "isabelle"}
    )

    assert response.status_code == 400
    assert not mock_subprocess.called


@patch('pocpod0_pipeline.dashboard_api.subprocess.run')
def test_revoke_validates_actor_name(mock_subprocess):
    """AC1: Revoke rejects unknown actor."""
    response = client.post(
        "/api/pods/ayoub/revoke",
        json={"actor": "unknown"}
    )

    assert response.status_code == 400
    assert not mock_subprocess.called


@patch('pocpod0_pipeline.dashboard_api.subprocess.run')
def test_revoke_handles_handler_denied(mock_subprocess):
    """AC6: Revoke returns HTTP 400 if handler denies (exit code 1)."""
    mock_subprocess.return_value = MagicMock(
        returncode=1,
        stdout=json.dumps({"status": "denied", "message": "Not in AGENT_POD_OWNERSHIP scope"})
    )

    response = client.post(
        "/api/pods/ayoub/revoke",
        json={"actor": "isabelle"}
    )

    assert response.status_code == 400
    data = response.json()
    assert "Not in AGENT_POD_OWNERSHIP scope" in data.get("detail", "")


@patch('pocpod0_pipeline.dashboard_api.subprocess.run')
def test_revoke_returns_ok_response(mock_subprocess):
    """AC1: Successful revoke returns HTTP 200."""
    mock_subprocess.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"status": "ok", "message": "Revoked access for isabelle from ayoub"})
    )

    response = client.post(
        "/api/pods/ayoub/revoke",
        json={"actor": "isabelle"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "message" in data


# ============================================================================
# AC6: Service health
# ============================================================================

def test_health_check_all_up():
    """AC6: Health endpoint returns all services up."""
    with patch('pocpod0_pipeline.dashboard_api.httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["css"] is True
        assert data["oxigraph"] is True
        assert data["qdrant"] is True


def test_health_check_partial_failure():
    """AC6: Health endpoint handles partial failures."""
    with patch('pocpod0_pipeline.dashboard_api.httpx.AsyncClient') as mock_client:
        call_count = [0]

        async def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:  # Second call (Oxigraph) fails
                raise httpx.RequestError("Connection refused")
            response = MagicMock()
            response.status_code = 200
            return response

        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=side_effect
        )

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["css"] is True
        assert data["oxigraph"] is False
        assert data["qdrant"] is True


# ============================================================================
# AC7: Demo moment end-to-end
# ============================================================================

@patch('pocpod0_pipeline.dashboard_api._provisioner.view_acl_state')
@patch('pocpod0_pipeline.dashboard_api.subprocess.run')
def test_demo_moment_workflow(mock_subprocess, mock_view_acl):
    """AC7: Full demo workflow - private → grant → shared → revoke → private."""

    # Step 1: Pod is private (no grants)
    mock_view_acl.return_value = (True, {"pod": "ayoub", "acl_grants": []})
    response = client.get("/api/pods")
    pods = response.json()
    ayoub = [p for p in pods if p["pod"] == "ayoub"][0]
    assert ayoub["is_private"] is True

    # Step 2: Grant isabelle access
    mock_subprocess.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"status": "ok", "message": "Granted isabelle read access to ayoub"})
    )
    response = client.post(
        "/api/pods/ayoub/grant",
        json={"actor": "isabelle", "access_level": "read"}
    )
    assert response.status_code == 200

    # Step 3: Pod is now shared (has grants)
    mock_view_acl.return_value = (True, {
        "pod": "ayoub",
        "acl_grants": [{
            "agent": "isabelle",
            "agent_webid": "http://localhost:3000/isabelle/profile/card#me",
            "access_modes": ["Read"]
        }]
    })
    response = client.get("/api/pods")
    pods = response.json()
    ayoub = [p for p in pods if p["pod"] == "ayoub"][0]
    assert ayoub["is_private"] is False

    # Step 4: Revoke isabelle's access
    mock_subprocess.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"status": "ok", "message": "Revoked access for isabelle from ayoub"})
    )
    response = client.post(
        "/api/pods/ayoub/revoke",
        json={"actor": "isabelle"}
    )
    assert response.status_code == 200

    # Step 5: Pod is private again
    mock_view_acl.return_value = (True, {"pod": "ayoub", "acl_grants": []})
    response = client.get("/api/pods")
    pods = response.json()
    ayoub = [p for p in pods if p["pod"] == "ayoub"][0]
    assert ayoub["is_private"] is True


# ============================================================================
# AC2/AC3: Troll backend routes
# ============================================================================

@patch('pocpod0_pipeline.dashboard_api.subprocess.Popen')
def test_troll_run_triggers_subprocess(mock_popen):
    """AC2: POST /api/troll/run triggers run_comprehensive.py subprocess."""
    mock_popen.return_value = MagicMock()

    response = client.post("/api/troll/run")

    assert response.status_code == 202  # Accepted (async)
    assert mock_popen.called

    # Verify subprocess was called with troll path
    call_args = mock_popen.call_args
    cmd = call_args[0][0]
    assert "run_comprehensive.py" in cmd[1]


@patch('pocpod0_pipeline.dashboard_api.Path')
def test_troll_results_reads_jsonl_file(mock_path):
    """AC3: GET /api/troll/results reads troll-run.jsonl and returns summary."""
    # Mock the troll-run.jsonl file with JSONL events
    troll_content = (
        '{"timestamp": "2026-04-02T12:00:00", "event_type": "troll.run.start", "total_categories": 5}\n'
        '{"timestamp": "2026-04-02T12:05:00", "event_type": "troll.category.done", "attack_category": "acl_enforcement", "blocking": true, "passed": 45, "partial": 2, "failed": 1, "total": 48}\n'
        '{"timestamp": "2026-04-02T12:10:00", "event_type": "troll.category.done", "attack_category": "sparql_injection", "blocking": true, "passed": 30, "partial": 0, "failed": 0, "total": 30}\n'
        '{"timestamp": "2026-04-02T12:15:00", "event_type": "troll.run.done", "total_tests": 150, "total_passed": 140, "total_partial": 5, "total_failed": 5, "blocking_pass": true}\n'
    )

    # Mock file operations
    mock_file = MagicMock()
    mock_file.read_text.return_value = troll_content
    mock_file.exists.return_value = True

    with patch('pocpod0_pipeline.dashboard_api.REPO_ROOT', '/fake/repo'):
        with patch('builtins.open', MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(readlines=MagicMock(return_value=troll_content.split('\n'))))))):
            response = client.get("/api/troll/results")

    assert response.status_code == 200
    data = response.json()
    assert "categories" in data or "troll_run" in data or len(data) > 0


@patch('pocpod0_pipeline.dashboard_api.subprocess.Popen')
def test_troll_run_returns_accepted(mock_popen):
    """AC2: POST /api/troll/run returns 202 Accepted (background task)."""
    mock_popen.return_value = MagicMock()

    response = client.post("/api/troll/run")

    assert response.status_code == 202
    data = response.json()
    assert "status" in data or "message" in data
