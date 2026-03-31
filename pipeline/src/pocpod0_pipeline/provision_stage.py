"""Pipeline Stage 0: Provision pods and seed community data.

This stage runs first in the pipeline to:
1. Create all pods via CSS
2. Apply access-log ACLs to all pods
3. Seed the school-community pod with dietary aggregate data

Designed to be invoked as: python -m pocpod0_pipeline.provision_stage
"""

import os
import sys
from pathlib import Path

import requests

from pocpod0_pipeline.provision_pods import PodProvisioner
from pocpod0_pipeline.utils import log_event


def _get_css_base_url() -> str:
    """Resolve CSS base URL from environment or default.

    Uses http://localhost:3000 as default when running outside Docker.
    """
    css_base_url = os.environ.get("CSS_BASE_URL", "http://localhost:3000")

    # For inter-container communication within Docker network
    if os.environ.get("CONTAINER_CONTEXT") == "docker" and "CSS_BASE_URL" not in os.environ:
        css_base_url = "http://community-solid-server:3000"

    return css_base_url.rstrip("/")


def _get_config_path() -> Path:
    """Locate pod-config.yaml from the project structure.

    When run as a module from pipeline/src/pocpod0_pipeline/provision_stage.py:
    - script_file: .../pipeline/src/pocpod0_pipeline/provision_stage.py
    - pipeline_dir: .../pipeline
    - project_root: .../pocpod0
    - config_path: .../pocpod0/infra/css/pods/pod-config.yaml
    """
    script_file = Path(__file__).resolve()
    pipeline_dir = script_file.parent.parent.parent  # up to pipeline/
    project_root = pipeline_dir.parent  # up to project root
    config_path = project_root / "infra" / "css" / "pods" / "pod-config.yaml"
    return config_path


def _seed_community_pod(css_base_url: str) -> bool:
    """Seed school-community pod with dietary aggregate data.

    Puts camp-dietary-aggregate.ttl to /school-community/camp/dietary-aggregate-2026
    with provisioner WebID authorization.

    Args:
        css_base_url: Base URL of Community Solid Server

    Returns:
        True on success, False on failure
    """
    # Locate seed file
    script_file = Path(__file__).resolve()
    pipeline_dir = script_file.parent.parent.parent
    project_root = pipeline_dir.parent
    seed_file = project_root / "data" / "seeds" / "camp-dietary-aggregate.ttl"

    if not seed_file.exists():
        log_event("provision.seed.error", "ERROR", {
            "reason": "seed_file_not_found",
            "file": str(seed_file)
        })
        print(f"❌ Seed file not found: {seed_file}")
        return False

    # Read seed content
    try:
        seed_content = seed_file.read_text()
    except Exception as e:
        log_event("provision.seed.error", "ERROR", {
            "reason": "seed_file_read_error",
            "error": str(e)
        })
        print(f"❌ Failed to read seed file: {e}")
        return False

    # Prepare authorization header using provisioner WebID
    provisioner_webid = f"{css_base_url}/provisioner/profile/card#me"
    headers = {
        "Authorization": f"WebID {provisioner_webid}",
        "Content-Type": "text/turtle",
    }

    # Target URL for the dietary aggregate resource
    url = f"{css_base_url}/school-community/camp/dietary-aggregate-2026"

    print(f"Seeding community pod...", end=" ", flush=True)
    try:
        resp = requests.put(url, data=seed_content, headers=headers, timeout=10)

        # CSS returns 201 (created) or 205 (reset/updated)
        if resp.status_code in (201, 205):
            print(f"✅")
            log_event("provision.seed.complete", "INFO", {
                "url": url,
                "status_code": resp.status_code
            })
            return True
        else:
            # If the container doesn't exist, CSS may return 404 or 409
            # In that case, we need to create the container first
            if resp.status_code == 404:
                print(f"(container missing, creating...)", end=" ", flush=True)
                container_url = f"{css_base_url}/school-community/camp/"
                try:
                    # Try to create the container with a simple PUT
                    container_resp = requests.put(container_url, headers=headers, timeout=10)
                    if container_resp.status_code not in (201, 205):
                        log_event("provision.seed.error", "ERROR", {
                            "reason": "container_creation_failed",
                            "container_url": container_url,
                            "status_code": container_resp.status_code
                        })
                        print(f"❌ Failed to create container (HTTP {container_resp.status_code})")
                        return False

                    # Retry the resource PUT
                    resp = requests.put(url, data=seed_content, headers=headers, timeout=10)
                    if resp.status_code in (201, 205):
                        print(f"✅")
                        log_event("provision.seed.complete", "INFO", {
                            "url": url,
                            "status_code": resp.status_code,
                            "container_created": True
                        })
                        return True
                    else:
                        log_event("provision.seed.error", "ERROR", {
                            "reason": "resource_put_failed",
                            "url": url,
                            "status_code": resp.status_code
                        })
                        print(f"❌ Failed to seed resource (HTTP {resp.status_code})")
                        return False
                except Exception as e:
                    log_event("provision.seed.error", "ERROR", {
                        "reason": "container_creation_exception",
                        "error": str(e)
                    })
                    print(f"❌ {e}")
                    return False
            else:
                log_event("provision.seed.error", "ERROR", {
                    "reason": "seed_put_failed",
                    "url": url,
                    "status_code": resp.status_code,
                    "response": resp.text[:200]
                })
                print(f"❌ Failed (HTTP {resp.status_code}): {resp.text[:100]}")
                return False
    except requests.RequestException as e:
        log_event("provision.seed.error", "ERROR", {
            "reason": "network_error",
            "error": str(e)
        })
        print(f"❌ {e}")
        return False


def main() -> None:
    """Main entry point for Stage 0: provision pods and seed community data."""
    css_base_url = _get_css_base_url()
    config_path = _get_config_path()

    print(f"Using CSS_BASE_URL: {css_base_url}")
    print(f"Using config: {config_path}\n")

    # Provision all pods (creates pods and applies ACLs)
    provisioner = PodProvisioner(css_base_url, str(config_path))
    results = provisioner.provision_all()

    # Seed community pod with dietary aggregate
    seed_ok = _seed_community_pod(css_base_url)

    # Exit with non-zero if any pods failed to create or seed failed
    if results["failed"] or results["acl_failed"] or not seed_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
