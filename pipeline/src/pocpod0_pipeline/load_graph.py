"""Graph loader: RDF triples from CSS Pods → Oxigraph with provenance.

Strategy: Named graphs (Option A) as primary mechanism.
Each Pod resource's triples are loaded into a named graph identified by the
Pod resource URI. This enables efficient provenance queries and cascade delete.

The graph URI == Pod resource URI, e.g.:
  http://localhost:3000/ayoub/learning/assessment/stmt-uuid.ttl

Error handling: log+continue — individual resource failures never abort the run.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from rdflib import Graph, Namespace

from pocpod0_pipeline.utils import (
    CSS_BASE_URL,
    PROVISIONER_WEBID,
    log_event,
    provisioner_headers,
    repo_root,
    schemas_dir,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OXIGRAPH_BASE_URL = os.environ.get("OXIGRAPH_BASE_URL", "http://localhost:7878")

# Named graph for OSLO schema triples
SCHEMA_GRAPH_URI = "https://poc-pod0.edu/vocab/schema"

# Content-type for CSS link-following (list pod contents)
CSS_TURTLE = "text/turtle"
CSS_ACCEPT_TURTLE = "text/turtle"

# Validate PROVISIONER_WEBID at import time — missing/empty breaks all CSS requests
if not PROVISIONER_WEBID:
    raise RuntimeError(
        "PROVISIONER_WEBID is not set. "
        "Ensure CSS_BASE_URL env var is configured and utils.PROVISIONER_WEBID is non-empty."
    )


# ---------------------------------------------------------------------------
# CSS helpers — enumerate and fetch Pod resources
# ---------------------------------------------------------------------------

def _auth_headers(accept: str = "text/turtle") -> Dict[str, str]:
    """Headers for CSS authenticated GET requests (provisioner WebID)."""
    return {
        "Authorization": f"WebID {PROVISIONER_WEBID}",
        "Accept": accept,
    }


def _list_pod_resources(pod_name: str, css_base: str) -> List[str]:
    """Return full CSS URLs of all Turtle resources in a Pod's learning/ container.

    Walks the pod's learning/ container recursively via LDP container listings.
    Returns list of resource URIs that end with .ttl.
    """
    resources: List[str] = []
    base = css_base.rstrip("/")
    css_host = urlparse(css_base).netloc
    containers_to_visit = [f"{base}/{pod_name}/learning/"]
    visited: set = set()  # P-1: cycle detection

    while containers_to_visit:
        container_url = containers_to_visit.pop(0)
        if container_url in visited:
            continue
        visited.add(container_url)
        try:
            resp = requests.get(container_url, headers=_auth_headers(), timeout=10)
            if resp.status_code == 404:
                # Container doesn't exist yet — skip silently
                continue
            if resp.status_code not in (200, 205):
                log_event("load_graph.pod.list_error", "WARN", {
                    "container": container_url,
                    "status": resp.status_code,
                })
                continue

            g = Graph()
            g.parse(data=resp.text, format="turtle", publicID=container_url)

            # LDP containers use ldp:contains
            LDP = Namespace("http://www.w3.org/ns/ldp#")
            for _, _, obj in g.triples((None, LDP.contains, None)):
                uri = str(obj)
                # P-2: reject URIs pointing to a different host
                if urlparse(uri).netloc != css_host:
                    log_event("load_graph.pod.ssrf_rejected", "WARN", {"uri": uri})
                    continue
                if uri.endswith(".ttl"):
                    resources.append(uri)
                elif uri.endswith("/"):
                    containers_to_visit.append(uri)
        except Exception as exc:
            log_event("load_graph.pod.list_error", "ERROR", {
                "container": container_url,
                "error": str(exc),
            })

    return resources


def _list_all_pod_resources(css_base: str) -> List[Tuple[str, str]]:
    """Return (pod_name, resource_uri) pairs for all learner pods.

    Discovers pods by listing the CSS root container.
    Skips system pods (provisioner).
    """
    base = css_base.rstrip("/")
    root_url = f"{base}/"
    result: List[Tuple[str, str]] = []

    try:
        resp = requests.get(root_url, headers=_auth_headers(), timeout=10)
        if resp.status_code not in (200, 205):
            log_event("load_graph.css.root_error", "ERROR", {
                "status": resp.status_code,
                "url": root_url,
            })
            return result

        g = Graph()
        g.parse(data=resp.text, format="turtle", publicID=root_url)
        LDP = Namespace("http://www.w3.org/ns/ldp#")
        css_host = urlparse(css_base).netloc
        for _, _, obj in g.triples((None, LDP.contains, None)):
            uri = str(obj)
            # P-2: reject cross-host URIs
            if urlparse(uri).netloc != css_host:
                log_event("load_graph.css.ssrf_rejected", "WARN", {"uri": uri})
                continue
            # Only process LDP containers (URI ends with "/"), skip plain resources
            if not uri.endswith("/"):
                continue
            pod_name = uri.rstrip("/").split("/")[-1]
            if not pod_name:  # P-6: guard against empty pod name
                continue
            if pod_name in ("provisioner",):
                continue
            pod_resources = _list_pod_resources(pod_name, css_base)
            for res_uri in pod_resources:
                result.append((pod_name, res_uri))
    except Exception as exc:
        log_event("load_graph.css.root_error", "ERROR", {"error": str(exc)})

    return result


def _fetch_turtle(resource_uri: str) -> Optional[str]:
    """Fetch Turtle content from a CSS Pod resource. Returns None on failure."""
    try:
        resp = requests.get(
            resource_uri,
            headers=_auth_headers(accept="text/turtle"),
            timeout=10,
        )
        if resp.status_code in (200, 205):
            return resp.text
        log_event("load_graph.resource.fetch_error", "WARN", {
            "resource_uri": resource_uri,
            "status": resp.status_code,
        })
        return None
    except Exception as exc:
        log_event("load_graph.resource.fetch_error", "ERROR", {
            "resource_uri": resource_uri,
            "error": str(exc),
        })
        return None


# ---------------------------------------------------------------------------
# Oxigraph helpers
# ---------------------------------------------------------------------------

def _load_turtle_to_graph(
    turtle_content: str,
    graph_uri: str,
    oxigraph_base: str,
) -> bool:
    """POST Turtle content to Oxigraph store endpoint, into a named graph.

    Returns True on success.
    """
    url = f"{oxigraph_base.rstrip('/')}/store"
    params = {"graph": graph_uri}
    try:
        resp = requests.post(
            url,
            params=params,
            data=turtle_content.encode("utf-8"),
            headers={"Content-Type": "text/turtle"},
            timeout=30,
        )
        if resp.status_code in (200, 201, 204):
            return True
        log_event("load_graph.oxigraph.store_error", "WARN", {
            "graph_uri": graph_uri,
            "status": resp.status_code,
            "response": resp.text[:200],
        })
        return False
    except Exception as exc:
        log_event("load_graph.oxigraph.store_error", "ERROR", {
            "graph_uri": graph_uri,
            "error": str(exc),
        })
        return False


# ---------------------------------------------------------------------------
# Core loading logic
# ---------------------------------------------------------------------------

def load_resource(
    resource_uri: str,
    pod_name: str,
    oxigraph_base: str,
) -> int:
    """Load a single Pod resource into Oxigraph. Returns triple count or -1 on error."""
    turtle_content = _fetch_turtle(resource_uri)
    if turtle_content is None:
        return -1

    # Count triples for reporting
    try:
        g = Graph()
        g.parse(data=turtle_content, format="turtle")
        triple_count = len(g)
    except Exception as exc:
        log_event("load_graph.resource.parse_error", "ERROR", {
            "resource_uri": resource_uri,
            "error": str(exc),
        })
        return -1

    # Load into named graph identified by the Pod resource URI (Option A)
    ok = _load_turtle_to_graph(turtle_content, resource_uri, oxigraph_base)
    if not ok:
        return -1

    log_event("load_graph.resource.loaded", "INFO", {
        "pod": pod_name,
        "resource": resource_uri,
        "triple_count": triple_count,
    })
    return triple_count


def load_from_pods(
    css_base: str = CSS_BASE_URL,
    oxigraph_base: str = OXIGRAPH_BASE_URL,
) -> Dict:
    """Enumerate all learner Pod resources and load them into Oxigraph.

    Returns summary dict with total_resources, total_triples, failed counts.
    """
    log_event("load_graph.run.start", "INFO", {
        "css_base": css_base,
        "oxigraph_base": oxigraph_base,
    })

    log_event("load_graph.discovery.start", "INFO", {"css_base": css_base})
    pod_resources = _list_all_pod_resources(css_base)
    total_resources = len(pod_resources)
    log_event("load_graph.resources.discovered", "INFO", {"total": total_resources})

    total_triples = 0
    failed = 0

    for pod_name, resource_uri in pod_resources:
        try:
            count = load_resource(resource_uri, pod_name, oxigraph_base)
            if count < 0:
                failed += 1
            else:
                total_triples += count
        except Exception as exc:
            log_event("load_graph.resource.failed", "ERROR", {
                "resource_uri": resource_uri,
                "error": str(exc),
            })
            failed += 1

    log_event("load_graph.run.complete", "INFO", {
        "total_resources": total_resources,
        "total_triples": total_triples,
        "failed": failed,
    })
    return {
        "total_resources": total_resources,
        "total_triples": total_triples,
        "failed": failed,
    }


# ---------------------------------------------------------------------------
# Task 4: Schema loader
# ---------------------------------------------------------------------------

def load_schemas(
    schemas_path: Optional[Path] = None,
    oxigraph_base: str = OXIGRAPH_BASE_URL,
) -> int:
    """Load OSLO schema files into Oxigraph under the schema named graph.

    Returns total number of schema triples loaded.
    """
    if schemas_path is None:
        schemas_path = schemas_dir()

    schema_files = list(schemas_path.glob("*.ttl"))
    if not schema_files:
        log_event("load_graph.schema.no_files", "WARN", {"path": str(schemas_path)})
        return 0

    # Merge all schema files into one graph, load as a single named graph
    merged = Graph()
    for schema_file in schema_files:
        try:
            merged.parse(str(schema_file), format="turtle")
            log_event("load_graph.schema.parsed", "DEBUG", {
                "file": schema_file.name,
            })
        except Exception as exc:
            log_event("load_graph.schema.parse_error", "ERROR", {
                "file": str(schema_file),
                "error": str(exc),
            })

    if len(merged) == 0:
        log_event("load_graph.schema.empty", "WARN", {
            "path": str(schemas_path),
            "detail": "All schema files failed to parse — skipping POST to avoid overwriting existing schema.",
        })
        return 0

    turtle_data = merged.serialize(format="turtle")
    ok = _load_turtle_to_graph(turtle_data, SCHEMA_GRAPH_URI, oxigraph_base)
    triple_count = len(merged) if ok else 0

    log_event("load_graph.schema.loaded", "INFO", {
        "graph_uri": SCHEMA_GRAPH_URI,
        "triple_count": triple_count,
        "schema_files": [f.name for f in schema_files],
    })
    return triple_count


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load RDF triples from CSS Pods into Oxigraph with provenance"
    )
    parser.add_argument(
        "--css-base-url",
        default=os.environ.get("CSS_BASE_URL", CSS_BASE_URL),
        help="CSS base URL (default: http://localhost:3000)",
    )
    parser.add_argument(
        "--oxigraph-url",
        default=os.environ.get("OXIGRAPH_BASE_URL", OXIGRAPH_BASE_URL),
        help="Oxigraph base URL (default: http://localhost:7878)",
    )
    parser.add_argument(
        "--load-schema",
        action="store_true",
        help="Also load OSLO schema files from data/schemas/",
    )
    args = parser.parse_args()

    if args.load_schema:
        try:
            schema_count = load_schemas(oxigraph_base=args.oxigraph_url)
            log_event("load_graph.schema.summary", "INFO", {"schema_triples": schema_count})
        except Exception as exc:
            log_event("load_graph.schema.fatal", "ERROR", {"error": str(exc)})
            sys.exit(1)

    result = load_from_pods(
        css_base=args.css_base_url,
        oxigraph_base=args.oxigraph_url,
    )
    sys.exit(0 if result["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
