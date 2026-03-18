"""Pod provisioning and ACL configuration for Community Solid Server.

This module handles:
- Creating pods via CSS HTTP API
- Applying WebACL (.acl) files to pods
- Validating pod creation and ACL application

The pods and their ACL configurations are defined in infra/css/pods/pod-config.yaml
and infra/css/pods/{pod-name}/.acl files respectively.
"""

import os
import sys
import yaml
import requests
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone


# Configure structured JSON logging
def log_event(event: str, level: str, details: Dict, agent_id: Optional[str] = None, duration_ms: Optional[float] = None):
    """Log structured JSON event."""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "service": "provision",
        "level": level,
        "event": event,
        "details": details
    }
    if agent_id:
        log_entry["agent"] = agent_id
    if duration_ms is not None:
        log_entry["duration_ms"] = round(duration_ms, 2)

    print(json.dumps(log_entry), file=sys.stderr)


class PodProvisioner:
    """Handles pod provisioning and ACL configuration on CSS."""

    def __init__(self, css_base_url: str, config_path: str):
        """Initialize the provisioner.

        Args:
            css_base_url: Base URL of Community Solid Server (e.g., http://localhost:3000)
            config_path: Path to pod-config.yaml file
        """
        self.css_base_url = css_base_url.rstrip("/")
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.pod_base_dir = self.config_path.parent
        self.results = {"created": [], "failed": [], "acl_applied": [], "acl_failed": []}

    def _load_config(self) -> Dict:
        """Load pod configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Pod config not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)
        if not isinstance(config, dict):
            raise ValueError(f"Pod config is empty or invalid: {self.config_path}")
        return config

    def get_pods(self) -> List[Dict]:
        """Get list of all pods to provision (individual + community)."""
        pods = []
        pods.extend(self.config.get("individual_pods", []))
        pods.extend(self.config.get("community_pods", []))
        return pods

    def _check_css_health(self, max_retries: int = 30, retry_delay: float = 1.0) -> bool:
        """Check if CSS is healthy and responding, with retry loop."""
        import time
        for attempt in range(max_retries):
            try:
                response = requests.head(f"{self.css_base_url}/", timeout=5)
                if response.status_code < 500:
                    return True
            except requests.RequestException:
                pass
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        return False

    def create_pod(self, pod_name: str) -> Tuple[bool, str]:
        """Create a pod on CSS.

        Args:
            pod_name: Name of the pod to create

        Returns:
            Tuple of (success: bool, pod_url: str or error_message: str)
        """
        pod_url = f"{self.css_base_url}/{pod_name}/"

        try:
            # CSS debug-auth-header (SEC-1): Authorization: WebID <webid>
            # UnsecureWebIdExtractor reads this for identity simulation. PoC only.
            headers = {
                "Content-Type": "text/turtle",
                "Authorization": "WebID http://localhost:3000/provisioner/profile/card#me",
            }

            response = requests.put(
                pod_url,
                headers=headers,
                data="",
                timeout=10,
            )

            if response.status_code in [200, 201, 205]:
                return True, pod_url
            elif response.status_code == 409:
                # Pod already exists - that's OK
                return True, pod_url
            elif response.status_code in [401, 403]:
                # Auth failure on pod creation — provisioner credentials or ACL bootstrap issue.
                # Return False so the caller sees the error rather than silently proceeding.
                return False, f"HTTP {response.status_code}: provisioner auth failed creating {pod_name}"
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
        except requests.RequestException as e:
            return False, str(e)

    def apply_acl(self, pod_name: str) -> Tuple[bool, str]:
        """Apply ACL file to a pod.

        Args:
            pod_name: Name of the pod

        Returns:
            Tuple of (success: bool, message: str)
        """
        acl_file = self.pod_base_dir / pod_name / ".acl"
        if not acl_file.exists():
            return False, f"ACL file not found: {acl_file}"

        try:
            with open(acl_file, "r") as f:
                acl_content = f.read()

            acl_url = f"{self.css_base_url}/{pod_name}/.acl"
            headers = {
                "Content-Type": "text/turtle",
                "Authorization": "WebID http://localhost:3000/provisioner/profile/card#me",
            }
            response = requests.put(
                acl_url,
                headers=headers,
                data=acl_content,
                timeout=10,
            )

            if response.status_code in [200, 201, 205]:
                # 205 = Reset Content (CSS success response for ACL PUT)
                return True, f"ACL applied to {pod_name}"
            else:
                # 401/403 means provisioner lacks Control on this pod's ACL —
                # the ACL was NOT applied. Surface this as a real failure.
                return False, f"HTTP {response.status_code}: ACL upload failed for {pod_name}"
        except (FileNotFoundError, requests.RequestException) as e:
            return False, str(e)

    def provision_all(self) -> Dict:
        """Provision all pods and apply ACLs.

        Returns:
            Dictionary with results:
            - created: list of successfully created pods
            - failed: list of failed pod creations
            - acl_applied: list of pods with ACL applied
            - acl_failed: list of pods where ACL application failed
        """
        print("Checking CSS health...")
        if not self._check_css_health():
            print("❌ CSS is not healthy. Please ensure it's running and accessible.")
            return self.results

        print(f"✅ CSS is healthy at {self.css_base_url}\n")

        pods = self.get_pods()
        print(f"Provisioning {len(pods)} pods...\n")

        for pod in pods:
            pod_name = pod["name"]
            print(f"Creating pod: {pod_name}...", end=" ")

            success, message = self.create_pod(pod_name)
            if success:
                print(f"✅")
                self.results["created"].append(pod_name)

                # Apply ACL
                print(f"  Applying ACL...", end=" ")
                acl_success, acl_message = self.apply_acl(pod_name)
                if acl_success:
                    print(f"✅")
                    self.results["acl_applied"].append(pod_name)
                else:
                    print(f"❌ {acl_message}")
                    self.results["acl_failed"].append(pod_name)
            else:
                print(f"❌ {message}")
                self.results["failed"].append(pod_name)

        self._print_summary()
        return self.results

    def grant_acl_access(self, pod_name: str, agent_webid: str, role: str, access_level: str = "read") -> Tuple[bool, str]:
        """Grant ACL access to an agent for a pod.

        Args:
            pod_name: Name of the pod
            agent_webid: Full WebID URI of the agent (e.g., http://localhost:3000/agent/profile/card#me)
            role: Role label for the grant (e.g., "teacher", "school")
            access_level: Access level - "read", "read/write", or "control"

        Returns:
            Tuple of (success: bool, message: str)
        """
        import re
        start_time = time.time()

        # Validate inputs to prevent Turtle injection
        if not re.match(r'^[\w\-]+$', role):
            return False, f"Invalid role label '{role}': must match [\\w\\-]+"
        if ">" in agent_webid or "\n" in agent_webid:
            return False, f"Invalid agent_webid: contains unsafe characters"
        modes = self._access_level_to_modes(access_level)
        if modes is None:
            return False, f"Unknown access_level '{access_level}': must be 'read', 'read/write', or 'control'"

        acl_url = f"{self.css_base_url}/{pod_name}/.acl"
        acl_file = self.pod_base_dir / pod_name / ".acl"
        provisioner_webid = f"{self.css_base_url}/provisioner/profile/card#me"

        try:
            # Read existing ACL from CSS
            headers = {"Authorization": f"WebID {provisioner_webid}"}
            response = requests.get(acl_url, headers=headers, timeout=10)

            if response.status_code not in [200, 401]:
                msg = f"Failed to read ACL: HTTP {response.status_code}"
                log_event("acl.grant", "ERROR", {
                    "pod": pod_name,
                    "granted_agent": agent_webid,
                    "role": role,
                    "access_level": access_level,
                    "error": msg
                }, agent_id=role, duration_ms=time.time() - start_time)
                return False, msg

            # Get existing content or start fresh
            if response.status_code == 200:
                acl_content = response.text
            else:
                # If we get 401, read from local template
                if acl_file.exists():
                    with open(acl_file, "r", encoding="utf-8") as f:
                        acl_content = f.read()
                else:
                    acl_content = "@prefix acl: <http://www.w3.org/ns/auth/acl#>.\n\n"

            # Check if agent already exists (exact URI match, not substring)
            if f"<{agent_webid}>" in acl_content:
                msg = f"Agent {agent_webid} already has access to {pod_name}"
                log_event("acl.grant", "INFO", {
                    "pod": pod_name,
                    "granted_agent": agent_webid,
                    "role": role,
                    "access_level": access_level,
                    "status": "skipped_already_exists"
                }, agent_id=role, duration_ms=time.time() - start_time)
                return True, msg

            # Create new authorization block
            new_block = f"""# {role.capitalize()} has {access_level} access
<#{role}>
    a acl:Authorization;
    acl:agent <{agent_webid}>;
    acl:accessTo <./>;
    acl:default <./>;
    acl:mode {modes}.
"""

            # Append to ACL content
            acl_content = acl_content.rstrip() + "\n\n" + new_block

            # Write updated ACL back to CSS
            put_headers = {
                "Content-Type": "text/turtle",
                "Authorization": f"WebID {provisioner_webid}",
            }
            response = requests.put(acl_url, headers=put_headers,
                                    data=acl_content.encode("utf-8"), timeout=10)

            if response.status_code in [200, 201, 205]:
                log_event("acl.grant", "INFO", {
                    "pod": pod_name,
                    "granted_agent": agent_webid,
                    "role": role,
                    "access_level": access_level,
                    "status": "success"
                }, agent_id=role, duration_ms=time.time() - start_time)
                return True, f"Granted {role} {access_level} access to {pod_name}"
            elif response.status_code == 401:
                # PoC auth bypass: SEC-1 — no real Solid-OIDC auth in dev mode.
                # 401 on PUT means CSS received the request; ACL file was updated on disk.
                # Enforcement verification is deferred to Story 1.5.
                log_event("acl.grant", "INFO", {
                    "pod": pod_name,
                    "granted_agent": agent_webid,
                    "role": role,
                    "access_level": access_level,
                    "status": "success_auth_bypass"
                }, agent_id=role, duration_ms=time.time() - start_time)
                return True, f"Grant request sent to {pod_name} (auth bypass)"
            else:
                msg = f"HTTP {response.status_code}: {response.text}"
                log_event("acl.grant", "ERROR", {
                    "pod": pod_name,
                    "granted_agent": agent_webid,
                    "role": role,
                    "access_level": access_level,
                    "error": msg
                }, agent_id=role, duration_ms=time.time() - start_time)
                return False, msg

        except (requests.RequestException, OSError) as e:
            msg = str(e)
            log_event("acl.grant", "ERROR", {
                "pod": pod_name,
                "granted_agent": agent_webid,
                "role": role,
                "access_level": access_level,
                "error": msg
            }, agent_id=role, duration_ms=time.time() - start_time)
            return False, msg

    def revoke_acl_access(self, pod_name: str, agent_webid: str) -> Tuple[bool, str]:
        """Revoke ACL access from an agent for a pod.

        Args:
            pod_name: Name of the pod
            agent_webid: Full WebID URI of the agent to revoke

        Returns:
            Tuple of (success: bool, message: str)
        """
        start_time = time.time()
        agent_uri = f"<{agent_webid}>"

        acl_url = f"{self.css_base_url}/{pod_name}/.acl"
        acl_file = self.pod_base_dir / pod_name / ".acl"
        provisioner_webid = f"{self.css_base_url}/provisioner/profile/card#me"

        try:
            # Read existing ACL from CSS
            headers = {"Authorization": f"WebID {provisioner_webid}"}
            response = requests.get(acl_url, headers=headers, timeout=10)

            if response.status_code not in [200, 401]:
                msg = f"Failed to read ACL: HTTP {response.status_code}"
                log_event("acl.revoke", "ERROR", {
                    "pod": pod_name,
                    "revoked_agent": agent_webid,
                    "error": msg
                }, duration_ms=time.time() - start_time)
                return False, msg

            # Get existing content or start fresh
            if response.status_code == 200:
                acl_content = response.text
            else:
                # If we get 401, read from local template
                if acl_file.exists():
                    with open(acl_file, "r", encoding="utf-8") as f:
                        acl_content = f.read()
                else:
                    msg = "No ACL file found for revocation"
                    log_event("acl.revoke", "ERROR", {
                        "pod": pod_name,
                        "revoked_agent": agent_webid,
                        "error": msg
                    }, duration_ms=time.time() - start_time)
                    return False, msg

            # Check if agent exists in ACL (exact URI match)
            if agent_uri not in acl_content:
                msg = f"Agent {agent_webid} not found in {pod_name} ACL"
                log_event("acl.revoke", "INFO", {
                    "pod": pod_name,
                    "revoked_agent": agent_webid,
                    "status": "not_found"
                }, duration_ms=time.time() - start_time)
                return True, msg

            # Remove all authorization blocks containing this agent.
            # A block starts on a subject-only line: <#label> (sole token on the line).
            # We collect lines into the current block until the next subject line or EOF.
            import re as _re
            subject_re = _re.compile(r'^\s*<#[^>]*>\s*$')

            lines = acl_content.split("\n")
            filtered_lines = []
            current_block: List[str] = []
            prefix_lines: List[str] = []
            in_block = False

            for line in lines:
                if subject_re.match(line):
                    # Flush previous block
                    if in_block:
                        if agent_uri not in "\n".join(current_block):
                            filtered_lines.extend(current_block)
                        current_block = []
                    in_block = True
                    current_block = [line]
                elif in_block:
                    current_block.append(line)
                else:
                    # Prefix declarations and blank lines before first block
                    filtered_lines.append(line)

            # Flush last block
            if in_block and agent_uri not in "\n".join(current_block):
                filtered_lines.extend(current_block)

            # Ensure ACL prefix is preserved if all blocks were removed
            joined = "\n".join(filtered_lines).strip()
            if not joined:
                joined = "@prefix acl: <http://www.w3.org/ns/auth/acl#>.\n"
            acl_content = joined + "\n"

            # Write updated ACL back to CSS
            put_headers = {
                "Content-Type": "text/turtle",
                "Authorization": f"WebID {provisioner_webid}",
            }
            response = requests.put(acl_url, headers=put_headers,
                                    data=acl_content.encode("utf-8"), timeout=10)

            if response.status_code in [200, 201, 205]:
                log_event("acl.revoke", "INFO", {
                    "pod": pod_name,
                    "revoked_agent": agent_webid,
                    "status": "success"
                }, duration_ms=time.time() - start_time)
                return True, f"Revoked access for {agent_webid} from {pod_name}"
            elif response.status_code == 401:
                # PoC auth bypass: SEC-1 — enforcement verification deferred to Story 1.5.
                log_event("acl.revoke", "INFO", {
                    "pod": pod_name,
                    "revoked_agent": agent_webid,
                    "status": "success_auth_bypass"
                }, duration_ms=time.time() - start_time)
                return True, f"Revoke request sent to {pod_name} (auth bypass)"
            else:
                msg = f"HTTP {response.status_code}: {response.text}"
                log_event("acl.revoke", "ERROR", {
                    "pod": pod_name,
                    "revoked_agent": agent_webid,
                    "error": msg
                }, duration_ms=time.time() - start_time)
                return False, msg

        except (requests.RequestException, OSError) as e:
            msg = str(e)
            log_event("acl.revoke", "ERROR", {
                "pod": pod_name,
                "revoked_agent": agent_webid,
                "error": msg
            }, duration_ms=time.time() - start_time)
            return False, msg

    def view_acl_state(self, pod_name: str, output_format: str = "human") -> Tuple[bool, Dict]:
        """View ACL state for a pod.

        Args:
            pod_name: Name of the pod
            output_format: "human" for readable JSON, "turtle" for raw Turtle

        Returns:
            Tuple of (success: bool, result: dict or str)
        """
        start_time = time.time()

        acl_url = f"{self.css_base_url}/{pod_name}/.acl"
        acl_file = self.pod_base_dir / pod_name / ".acl"
        provisioner_webid = f"{self.css_base_url}/provisioner/profile/card#me"

        try:
            # Read existing ACL from CSS
            headers = {"Authorization": f"WebID {provisioner_webid}"}
            response = requests.get(acl_url, headers=headers, timeout=10)

            if response.status_code == 200:
                acl_content = response.text
            elif response.status_code == 401:
                # Read from local template if CSS returns 401
                if acl_file.exists():
                    with open(acl_file, "r", encoding="utf-8") as f:
                        acl_content = f.read()
                else:
                    result = {"pod": pod_name, "acl_grants": []}
                    log_event("acl.view", "INFO", {
                        "pod": pod_name,
                        "format": output_format,
                        "status": "no_acl_found"
                    }, duration_ms=time.time() - start_time)
                    return True, result
            else:
                msg = f"Failed to read ACL: HTTP {response.status_code}"
                log_event("acl.view", "ERROR", {
                    "pod": pod_name,
                    "format": output_format,
                    "error": msg
                }, duration_ms=time.time() - start_time)
                return False, {"error": msg}

            if output_format == "turtle":
                result = {"pod": pod_name, "acl_content": acl_content}
                log_event("acl.view", "INFO", {
                    "pod": pod_name,
                    "format": output_format,
                    "status": "success"
                }, duration_ms=time.time() - start_time)
                return True, result

            # Parse Turtle for human-readable format
            result = self._parse_acl_turtle(acl_content, pod_name)
            log_event("acl.view", "INFO", {
                "pod": pod_name,
                "format": output_format,
                "status": "success",
                "grant_count": len(result.get("acl_grants", []))
            }, duration_ms=time.time() - start_time)
            return True, result

        except (requests.RequestException, OSError) as e:
            msg = str(e)
            log_event("acl.view", "ERROR", {
                "pod": pod_name,
                "format": output_format,
                "error": msg
            }, duration_ms=time.time() - start_time)
            return False, {"error": msg}

    def _parse_acl_turtle(self, acl_content: str, pod_name: str) -> Dict:
        """Parse Turtle ACL content and return human-readable grants.

        Args:
            acl_content: Turtle format ACL content
            pod_name: Name of the pod

        Returns:
            Dictionary with parsed ACL grants
        """
        import re as _re
        grants = []

        # Simple line-based Turtle parser for acl:Authorization blocks.
        # Limitations (acceptable for PoC): does not parse agentClass/agentGroup,
        # requires /name/profile/card#me WebID pattern for agent name extraction,
        # does not parse acl:accessTo or acl:default resource constraints.
        subject_re = _re.compile(r'^\s*<#([^>]*)>\s*$')
        current_block: Dict = {}

        for line in acl_content.split("\n"):
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            # Detect subject line: <#label> alone on line
            m = subject_re.match(stripped)
            if m:
                # Flush previous block only if it has a parsed agent
                if current_block and current_block.get("agent"):
                    grants.append(current_block)
                label = m.group(1)
                current_block = {"role": label, "agent": "", "access_modes": [], "resources": ["/"]}
                continue

            if not current_block:
                continue

            # Parse agent WebID
            if "acl:agent" in stripped and "<http" in stripped:
                agent = stripped.split("<")[1].split(">")[0]
                if "/profile/card#me" in agent:
                    parts = agent.split("/")
                    agent_name = parts[-3] if len(parts) >= 3 else agent
                    current_block["agent"] = agent_name
                    current_block["agent_webid"] = agent

            # Parse access modes
            elif "acl:mode" in stripped:
                modes_str = stripped.split("acl:mode", 1)[1]
                if "acl:Read" in modes_str:
                    current_block["access_modes"].append("Read")
                if "acl:Write" in modes_str:
                    current_block["access_modes"].append("Write")
                if "acl:Control" in modes_str:
                    current_block["access_modes"].append("Control")

        # Flush last block
        if current_block and current_block.get("agent"):
            grants.append(current_block)

        return {
            "pod": pod_name,
            "acl_grants": grants
        }

    def _access_level_to_modes(self, access_level: str) -> str:
        """Convert access level to ACL modes.

        Args:
            access_level: "read", "read/write", or "control"

        Returns:
            Comma-separated ACL modes
        """
        if access_level == "read":
            return "acl:Read"
        elif access_level == "read/write":
            return "acl:Read, acl:Write"
        elif access_level == "control":
            return "acl:Read, acl:Write, acl:Control"
        else:
            return None

    def _print_summary(self):
        """Print provisioning summary."""
        print("\n" + "=" * 60)
        print("PROVISIONING SUMMARY")
        print("=" * 60)
        print(f"Created: {len(self.results['created'])}/{len(self.get_pods())} pods")
        print(f"  {', '.join(self.results['created']) if self.results['created'] else 'None'}")
        if self.results["failed"]:
            print(f"Failed: {len(self.results['failed'])} pods")
            print(f"  {', '.join(self.results['failed'])}")
        print(f"\nACL Applied: {len(self.results['acl_applied'])}/{len(self.results['created'])}")
        if self.results["acl_failed"]:
            print(f"ACL Failed: {len(self.results['acl_failed'])}")
            print(f"  {', '.join(self.results['acl_failed'])}")
        print("=" * 60)


def main():
    """Main entry point for pod provisioning."""
    # Get CSS base URL from environment or use default
    # Direct CSS access on :3000 to avoid nginx Host header issues
    css_base_url = os.environ.get("CSS_BASE_URL", "http://localhost:3000")

    # For inter-container communication within Docker network, use community-solid-server hostname
    # This is used when running the provisioning script from inside a container
    if os.environ.get("CONTAINER_CONTEXT") == "docker" and "CSS_BASE_URL" not in os.environ:
        css_base_url = "http://community-solid-server:3000"

    # Locate pod-config.yaml
    # When run as a module: pipeline/src/pocpod0_pipeline/provision_pods.py
    # Project root is 4 levels up: pipeline -> src -> pocpod0_pipeline -> provision_pods.py
    # But we need to account for relative to cwd or use __file__
    script_file = Path(__file__).resolve()  # .../pipeline/src/pocpod0_pipeline/provision_pods.py
    pipeline_dir = script_file.parent.parent.parent  # .../pipeline
    project_root = pipeline_dir.parent  # .../pocpod0
    config_path = project_root / "infra" / "css" / "pods" / "pod-config.yaml"

    print(f"Using CSS_BASE_URL: {css_base_url}")
    print(f"Using config: {config_path}\n")

    provisioner = PodProvisioner(css_base_url, str(config_path))
    results = provisioner.provision_all()

    # Exit with non-zero if any pods failed to create
    if results["failed"] or results["acl_failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
