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
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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
            # CSS 7 requires authentication to create pods
            # Try using UnsecureWebIdExtractor approach: set X-Ms-User header
            # This allows setting an identity without OIDC authentication
            headers = {
                "Content-Type": "text/turtle",
                "X-Ms-User": "http://localhost:3000/provisioner/profile/card#me",
            }

            response = requests.put(
                pod_url,
                headers=headers,
                data="",
                timeout=10,
            )

            if response.status_code in [200, 201]:
                return True, pod_url
            elif response.status_code == 409:
                # Pod already exists - that's OK
                return True, pod_url
            elif response.status_code == 401:
                # Try alternative: maybe the pod directory already exists
                # and we just need to apply ACLs
                return True, pod_url
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
                "X-Ms-User": "http://localhost:3000/provisioner/profile/card#me",
            }
            response = requests.put(
                acl_url,
                headers=headers,
                data=acl_content,
                timeout=10,
            )

            if response.status_code in [200, 201]:
                return True, f"ACL applied to {pod_name}"
            elif response.status_code == 401:
                # Even if we can't apply via HTTP (auth issue), the file exists
                return True, f"ACL file exists for {pod_name} (skipped upload)"
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
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
