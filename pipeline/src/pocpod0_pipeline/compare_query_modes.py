"""Graph-only vs Hybrid query comparison script.

Produces a structured JSON report and human-readable Markdown summary
comparing SPARQL-only vs SPARQL+Qdrant hybrid results for students
in Claire's authorized scope.

Usage (from repo root, with venv active):
    python -m pocpod0_pipeline.compare_query_modes
    python -m pocpod0_pipeline.compare_query_modes \\
        --query-text "struggling students quadratic equations" \\
        --output-dir data/reports/

Isolation note: runs on host; all services exposed on localhost ports.
No distrobox-host-exec needed for HTTP calls.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Skill path injection — handlers live outside the pipeline package
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[3]

# Load .env from repo root if present (OPENROUTER_API_KEY needed for Qdrant embeddings)
_env_file = _REPO_ROOT / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# Force host-side routing: comparison script runs on host, not in Docker.
# .env has Docker-internal hostnames (community-solid-server, oxigraph, qdrant).
# Override all service URLs to localhost so skill handlers connect via host ports.
os.environ["CSS_CONNECT_URL"] = os.environ.get("CSS_BASE_URL", "http://localhost:3000")
os.environ["CSS_IDENTIFIER_HOST"] = "localhost:3000"
os.environ["OXIGRAPH_URL"] = os.environ.get("OXIGRAPH_BASE_URL", "http://localhost:7878")
os.environ["QDRANT_URL"] = os.environ.get("QDRANT_BASE_URL", "http://localhost:6333")

_SPARQL_SKILL_DIR = _REPO_ROOT / "agents" / "skills" / "sparql-query"
_QDRANT_SKILL_DIR = _REPO_ROOT / "agents" / "skills" / "qdrant-search"

import importlib.util as _ilu

# Both handlers export `run_skill` — use importlib to avoid sys.path collision
_sparql_spec = _ilu.spec_from_file_location("sparql_handler", _SPARQL_SKILL_DIR / "handler.py")
_sparql_mod = _ilu.module_from_spec(_sparql_spec)  # type: ignore[arg-type]
sys.path.insert(0, str(_SPARQL_SKILL_DIR))
_sparql_spec.loader.exec_module(_sparql_mod)  # type: ignore[union-attr]
_sparql_run_skill = _sparql_mod.run_skill

_qdrant_spec = _ilu.spec_from_file_location("qdrant_handler", _QDRANT_SKILL_DIR / "handler.py")
_qdrant_mod = _ilu.module_from_spec(_qdrant_spec)  # type: ignore[arg-type]
sys.path.insert(0, str(_QDRANT_SKILL_DIR))
_qdrant_spec.loader.exec_module(_qdrant_mod)  # type: ignore[union-attr]
_qdrant_run_skill = _qdrant_mod.run_skill

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CSS_BASE_URL = os.environ.get("CSS_BASE_URL", "http://localhost:3000")

CLAIRE_WEBID = f"{CSS_BASE_URL}/claire/profile/card#me"

CLAIRE_SCOPE = [
    {"name": "ayoub",            "pod_uri": f"{CSS_BASE_URL}/ayoub/"},
    {"name": "claire-student-1", "pod_uri": f"{CSS_BASE_URL}/claire-student-1/"},
    {"name": "claire-student-2", "pod_uri": f"{CSS_BASE_URL}/claire-student-2/"},
]

DEFAULT_QUERY_TEXT = "struggling students quadratic equations"
DEFAULT_OUTPUT_DIR = str(_REPO_ROOT / "data" / "reports")
DEFAULT_STUDENTS = "ayoub,claire-student-1,claire-student-2"

# Out-of-scope pod used for AC4 enforcement check
OUT_OF_SCOPE_POD_URI = f"{CSS_BASE_URL}/fatima-child-1/"


# ---------------------------------------------------------------------------
# Graph-only query
# ---------------------------------------------------------------------------


def run_graph_only(pod_uri: str, agent_webid: str) -> dict[str, Any]:
    """Run SPARQL cross-context-query for a single student pod.

    Returns:
        {summary, result_count, latency_ms, status}
    """
    t0 = time.monotonic()
    result = _sparql_run_skill(
        query_type="cross-context-query",
        webid=agent_webid,
        role="tutor",
        params={"pod_uri": pod_uri, "agent_webid": agent_webid},
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    return {
        "status": result.get("status", "error"),
        "summary": result.get("summary", {}),
        "result_count": result.get("result_count", 0),
        "latency_ms": latency_ms,
        "error": result.get("error") or result.get("reason"),
    }


# ---------------------------------------------------------------------------
# Hybrid query (SPARQL + Qdrant)
# ---------------------------------------------------------------------------


def run_hybrid(pod_uri: str, query_text: str, agent_webid: str) -> dict[str, Any]:
    """Run hybrid query: SPARQL facts + Qdrant semantic enrichment.

    Qdrant results are filtered to pod_resource_uri matching the target pod prefix.

    Returns:
        {sparql_summary, qdrant_enrichments, qdrant_result_count, latency_ms, status}
    """
    t0 = time.monotonic()

    # SPARQL component
    sparql_result = _sparql_run_skill(
        query_type="cross-context-query",
        webid=agent_webid,
        role="tutor",
        params={"pod_uri": pod_uri, "agent_webid": agent_webid},
    )

    # Qdrant component (no pod-level ACL — embeddings derived from ACL-checked data)
    qdrant_result = _qdrant_run_skill(
        query=query_text,
        agent="claire-teacher",
        limit=10,
        score_threshold=0.6,  # slightly lower to get more candidates before filtering
    )

    latency_ms = int((time.monotonic() - t0) * 1000)

    # Filter Qdrant results to target pod prefix only
    qdrant_enrichments: list[dict[str, Any]] = []
    if qdrant_result.get("status") == "success":
        for r in qdrant_result.get("results", []):
            resource_uri = r.get("pod_resource_uri", "")
            if resource_uri.startswith(pod_uri):
                qdrant_enrichments.append({
                    "content_text": r.get("content_summary", ""),
                    "score": r.get("score", 0.0),
                    "pod_resource_uri": resource_uri,
                })

    sparql_status = sparql_result.get("status", "error")
    qdrant_status = qdrant_result.get("status", "error")
    combined_status = "success" if sparql_status == "success" else sparql_status

    return {
        "status": combined_status,
        "sparql_summary": sparql_result.get("summary", {}),
        "sparql_result_count": sparql_result.get("result_count", 0),
        "qdrant_enrichments": qdrant_enrichments,
        "qdrant_result_count": len(qdrant_enrichments),
        "qdrant_raw_status": qdrant_status,
        "latency_ms": latency_ms,
        "error": sparql_result.get("error") or sparql_result.get("reason"),
    }


# ---------------------------------------------------------------------------
# Delta computation
# ---------------------------------------------------------------------------


def compute_delta(graph_result: dict[str, Any], hybrid_result: dict[str, Any]) -> dict[str, Any]:
    """Identify semantic enrichments from Qdrant not captured as structured triples.

    Heuristic: any Qdrant result with score > 0.7 is a novel semantic enrichment.
    """
    novel_insights: list[str] = []
    for enrichment in hybrid_result.get("qdrant_enrichments", []):
        if enrichment.get("score", 0.0) > 0.7 and enrichment.get("content_text"):
            novel_insights.append(enrichment["content_text"][:300])

    hybrid_adds_value = len(novel_insights) > 0

    return {
        "novel_insights": novel_insights,
        "hybrid_adds_value": hybrid_adds_value,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(
    student_results: list[dict[str, Any]],
    query_text: str,
) -> dict[str, Any]:
    """Build the full JSON report structure.

    student_results: list of {name, pod_uri, graph_only, hybrid, delta, access_denied}
    """
    students_section: dict[str, Any] = {}
    total_latency = 0
    students_with_enrichment = 0
    qdrant_counts: list[int] = []

    for sr in student_results:
        name = sr["name"]
        pod_uri = sr["pod_uri"]

        if sr.get("access_denied"):
            students_section[name] = {
                "pod_uri": pod_uri,
                "access_denied": sr["access_denied"],
            }
            continue

        go = sr["graph_only"]
        hy = sr["hybrid"]
        delta = sr["delta"]

        total_latency += go.get("latency_ms", 0) + hy.get("latency_ms", 0)

        go_summary = go.get("summary", {})
        hy_summary = go_summary  # sparql_summary mirrors graph_only summary

        students_section[name] = {
            "pod_uri": pod_uri,
            "graph_only": {
                "result_count": go.get("result_count", 0),
                "activity_breakdown": go_summary.get("activity_breakdown", {}),
                "score_stats": go_summary.get("score_stats", {}),
                "mastery_events_count": len(go_summary.get("mastery_events", [])),
                "latency_ms": go.get("latency_ms", 0),
            },
            "hybrid": {
                "sparql_summary": {
                    "result_count": hy.get("sparql_result_count", 0),
                    "activity_breakdown": hy.get("sparql_summary", {}).get("activity_breakdown", {}),
                },
                "qdrant_enrichments": hy.get("qdrant_enrichments", []),
                "qdrant_result_count": hy.get("qdrant_result_count", 0),
                "latency_ms": hy.get("latency_ms", 0),
            },
            "delta": delta,
        }

        if delta.get("hybrid_adds_value"):
            students_with_enrichment += 1
        qdrant_counts.append(hy.get("qdrant_result_count", 0))

    in_scope = [sr for sr in student_results if not sr.get("access_denied")]
    avg_qdrant = round(sum(qdrant_counts) / len(qdrant_counts), 1) if qdrant_counts else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "query": query_text,
        "students": students_section,
        "aggregate": {
            "students_queried": len(in_scope),
            "students_with_hybrid_enrichment": students_with_enrichment,
            "avg_qdrant_results_per_student": avg_qdrant,
            "total_latency_ms": total_latency,
        },
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Graph-Only vs Hybrid Comparison Report",
        f"Generated: {report['generated_at'][:10]} | Query: \"{report['query']}\"",
        "",
    ]

    for name, data in report["students"].items():
        lines.append(f"## {name} ({name}/)")
        if data.get("access_denied"):
            lines.append(f"**Access denied:** {data['access_denied']}")
            lines.append("")
            continue

        go = data["graph_only"]
        hy = data["hybrid"]
        delta = data["delta"]

        breakdown = go.get("activity_breakdown", {})
        score_stats = go.get("score_stats", {})
        score_str = (
            f"avg score {score_stats['avg']}" if score_stats else "no scores"
        )
        lines.append(
            f"**Graph-only:** {go['result_count']} activities — "
            f"{breakdown} — {score_str}, "
            f"{go['mastery_events_count']} mastery events "
            f"({go['latency_ms']}ms)"
        )

        qdrant_count = hy["qdrant_result_count"]
        enrichment_preview = ""
        if hy["qdrant_enrichments"]:
            enrichment_preview = f" (e.g. \"{hy['qdrant_enrichments'][0]['content_text'][:80]}\")"
        lines.append(
            f"**Hybrid enrichment:** {qdrant_count} Qdrant results{enrichment_preview} "
            f"({hy['latency_ms']}ms)"
        )

        if delta["hybrid_adds_value"]:
            lines.append("**Delta:** ✓ Hybrid adds semantic context invisible in structured data")
        else:
            lines.append("**Delta:** ✗ No significant semantic enrichment above threshold")
        lines.append("")

    agg = report["aggregate"]
    pct = int(agg["students_with_hybrid_enrichment"] / agg["students_queried"] * 100) if agg["students_queried"] else 0
    lines += [
        "## Aggregate",
        f"- {agg['students_queried']} students queried, "
        f"{agg['students_with_hybrid_enrichment']} with hybrid enrichment ({pct}%)",
        f"- Avg {agg['avg_qdrant_results_per_student']} Qdrant enrichments per student",
        f"- Total elapsed: {agg['total_latency_ms'] / 1000:.1f}s",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare graph-only vs hybrid query results across Claire's student scope"
    )
    parser.add_argument(
        "--query-text",
        default=DEFAULT_QUERY_TEXT,
        help=f"Semantic query text for Qdrant (default: '{DEFAULT_QUERY_TEXT}')",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for report output (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--students",
        default=DEFAULT_STUDENTS,
        help=f"Comma-separated student slugs (default: {DEFAULT_STUDENTS})",
    )
    args = parser.parse_args()

    # Build scope from --students arg
    requested_names = [s.strip() for s in args.students.split(",")]
    scope = [s for s in CLAIRE_SCOPE if s["name"] in requested_names]
    if not scope:
        print(f"ERROR: No matching students found for: {args.students}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Graph-Only vs Hybrid Comparison")
    print(f"Query: \"{args.query_text}\"")
    print(f"Students: {[s['name'] for s in scope]}")
    print(f"{'='*60}\n")

    student_results: list[dict[str, Any]] = []
    t_total = time.monotonic()

    for student in scope:
        name = student["name"]
        pod_uri = student["pod_uri"]
        print(f"▶ {name} ({pod_uri})")

        # Graph-only
        print(f"  Running graph-only SPARQL...", end="", flush=True)
        go_result = run_graph_only(pod_uri, CLAIRE_WEBID)
        if go_result["status"] in ("denied", "error"):
            print(f" DENIED/ERROR: {go_result.get('error')}")
            student_results.append({
                "name": name,
                "pod_uri": pod_uri,
                "access_denied": f"not in scope: {go_result.get('error', 'access denied')}",
            })
            continue
        print(f" {go_result['result_count']} results ({go_result['latency_ms']}ms)")

        # Hybrid
        print(f"  Running hybrid (SPARQL + Qdrant)...", end="", flush=True)
        hy_result = run_hybrid(pod_uri, args.query_text, CLAIRE_WEBID)
        print(f" {hy_result['qdrant_result_count']} Qdrant enrichments ({hy_result['latency_ms']}ms)")

        # Delta
        delta = compute_delta(go_result, hy_result)
        value_str = "✓ adds value" if delta["hybrid_adds_value"] else "✗ no novel insights"
        print(f"  Delta: {value_str} ({len(delta['novel_insights'])} novel insights)\n")

        student_results.append({
            "name": name,
            "pod_uri": pod_uri,
            "graph_only": go_result,
            "hybrid": hy_result,
            "delta": delta,
        })

    # AC4: also test out-of-scope pod (fatima-child-1)
    print(f"▶ [AC4 check] fatima-child-1 (out of scope)")
    print(f"  Running graph-only SPARQL...", end="", flush=True)
    oos_go = run_graph_only(OUT_OF_SCOPE_POD_URI, CLAIRE_WEBID)
    print(f" status={oos_go['status']} results={oos_go['result_count']}")

    print(f"  Running hybrid...", end="", flush=True)
    oos_hy = run_hybrid(OUT_OF_SCOPE_POD_URI, args.query_text, CLAIRE_WEBID)
    oos_qdrant_filtered = [
        r for r in oos_hy.get("qdrant_enrichments", [])
        if r["pod_resource_uri"].startswith(OUT_OF_SCOPE_POD_URI)
    ]
    print(f" qdrant_filtered={len(oos_qdrant_filtered)}\n")

    student_results.append({
        "name": "fatima-child-1",
        "pod_uri": OUT_OF_SCOPE_POD_URI,
        "access_denied": (
            f"not in scope: {oos_go.get('error', 'access denied')}"
            if oos_go["status"] in ("denied", "error")
            else "access unexpectedly granted — investigate ACL configuration"
        ),
    })

    # Generate and save report
    report = generate_report(student_results, args.query_text)
    total_elapsed = time.monotonic() - t_total
    report["aggregate"]["total_latency_ms"] = int(total_elapsed * 1000)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    report_path = output_dir / f"graph-vs-hybrid-{timestamp}.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"Report saved: {report_path}")

    # Render and print Markdown summary
    md = render_markdown(report)
    print("\n" + md)

    print(f"\nTotal elapsed: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
