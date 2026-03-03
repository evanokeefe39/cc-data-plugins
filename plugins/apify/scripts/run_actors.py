# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.1.0",
#     "httpx>=0.27.0",
# ]
# ///
"""
EXECUTE phase script — dispatch Apify actor runs and poll for status.

Subcommands:
  dispatch  - Validate plan JSON, dispatch actor runs, record state
  poll      - Check status of running jobs
  status    - Show status of a pipeline run

All four gates are validated before dispatch. This is Layer 3 (script validation) —
the unbypassable final gate.
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import httpx

def _resolve_project_dir() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    cwd = Path.cwd()
    if (cwd / ".apify-plugin").exists():
        return cwd
    print(json.dumps({"error": "CLAUDE_PROJECT_DIR not set and .apify-plugin/ not found in cwd", "cwd": str(cwd)}), file=sys.stderr)
    sys.exit(1)

PROJECT_DIR = _resolve_project_dir()
DATA_DIR = PROJECT_DIR / ".apify-plugin" / "data"
DB_PATH = DATA_DIR / "datasets.duckdb"

APIFY_API_BASE = "https://api.apify.com/v2"


def get_apify_token() -> str:
    """Get Apify API token. Raises if not set."""
    from _token import get_apify_token as _get
    token = _get()
    if not token:
        print(json.dumps({
            "status": "blocked",
            "errors": ["No APIFY_TOKEN or APIFY_API_TOKEN set. Check .env or environment variables."],
        }))
        sys.exit(1)
    return token


def validate_plan(plan: dict) -> list[str]:
    """
    Validate plan JSON against all four gates.
    Returns list of error messages. Empty list = all gates pass.
    """
    errors = []

    # Gate 1 — Params Complete
    jobs = plan.get("jobs", [])
    if not jobs:
        errors.append("Gate 1 (Params): No jobs defined in plan.")

    for i, job in enumerate(jobs):
        actor_id = job.get("actor_id")
        if not actor_id:
            errors.append(f"Gate 1 (Params): Job {i} missing actor_id.")
        input_params = job.get("input", {})
        if not input_params:
            errors.append(f"Gate 1 (Params): Job {i} ({actor_id}) has no input parameters.")
        # Check maxItems is set (never unbounded)
        max_items = input_params.get("maxItems") or input_params.get("resultsLimit") or input_params.get("resultsPerPage") or input_params.get("maxCrawledPlacesPerSearch")
        if max_items is None:
            errors.append(f"Gate 1 (Params): Job {i} ({actor_id}) has no item limit set (maxItems/resultsLimit). Never run unbounded.")

    # Gate 2 — Cost Approved
    cost_approval = plan.get("cost_approval")
    if not cost_approval:
        errors.append("Gate 2 (Cost): No cost approval recorded. Present estimate and get user confirmation first.")
    elif not cost_approval.get("approved"):
        errors.append("Gate 2 (Cost): Cost not approved by user.")
    elif not cost_approval.get("timestamp"):
        errors.append("Gate 2 (Cost): Cost approval missing timestamp.")

    # Gate 3 — Scope Decided
    scope = plan.get("scope")
    valid_scopes = {"metadata_only", "with_media", "with_transcripts"}
    if not scope:
        errors.append("Gate 3 (Scope): No scope decision. User must choose: metadata_only, with_media, or with_transcripts.")
    elif scope not in valid_scopes:
        errors.append(f"Gate 3 (Scope): Invalid scope '{scope}'. Must be one of: {valid_scopes}")

    # Gate 4 — Destination Set
    destination = plan.get("destination")
    valid_destinations = {"local_duckdb", "local_files", "remote", "decide_later"}
    if not destination:
        errors.append("Gate 4 (Destination): No destination set. User must choose where data lands.")
    elif destination not in valid_destinations:
        errors.append(f"Gate 4 (Destination): Invalid destination '{destination}'. Must be one of: {valid_destinations}")

    return errors


def dispatch(plan: dict):
    """Dispatch actor runs after validation."""
    # Validate all four gates
    errors = validate_plan(plan)
    if errors:
        print(json.dumps({
            "status": "blocked",
            "errors": errors,
            "gates_failed": len(errors),
            "instruction": "Resolve all gate failures, rebuild the plan, and try again.",
        }, indent=2))
        sys.exit(2)

    token = get_apify_token()
    con = duckdb.connect(str(DB_PATH))

    # Create pipeline run
    pipeline_run_id = str(uuid.uuid4())
    session_id = plan.get("session_id", "unknown")
    user_request = plan.get("user_request", "")
    estimated_cost = plan.get("cost_approval", {}).get("estimated_cost", 0)

    con.execute("""
        INSERT INTO pipeline_runs (run_id, session_id, user_request, status, config, estimated_cost)
        VALUES (?, ?, ?, 'dispatching', ?, ?)
    """, [pipeline_run_id, session_id, user_request, json.dumps(plan), estimated_cost])

    client = httpx.Client(
        base_url=APIFY_API_BASE,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )

    results = []
    for i, job_spec in enumerate(plan["jobs"]):
        job_id = str(uuid.uuid4())
        actor_id = job_spec["actor_id"]
        input_params = job_spec.get("input", {})

        # Add timeout if specified
        timeout_secs = job_spec.get("timeout_secs")
        build = job_spec.get("build")

        # Record job as dispatching
        con.execute("""
            INSERT INTO apify_jobs (job_id, run_id, actor_id, status, dispatched_at)
            VALUES (?, ?, ?, 'dispatching', current_timestamp)
        """, [job_id, pipeline_run_id, actor_id])

        try:
            # Dispatch to Apify
            # Actor IDs use slash notation (apify/instagram-scraper) but the
            # REST API needs tilde (apify~instagram-scraper) in URL paths.
            api_actor_id = actor_id.replace("/", "~")

            params = {}
            if timeout_secs:
                params["timeout"] = timeout_secs
            if build:
                params["build"] = build

            resp = client.post(
                f"/acts/{api_actor_id}/runs",
                json=input_params,
                params=params,
            )

            if resp.status_code in (200, 201):
                run_data = resp.json().get("data", {})
                apify_run_id = run_data.get("id")
                dataset_id = run_data.get("defaultDatasetId")

                con.execute("""
                    UPDATE apify_jobs
                    SET apify_run_id = ?, dataset_id = ?, status = 'running'
                    WHERE job_id = ?
                """, [apify_run_id, dataset_id, job_id])

                results.append({
                    "job_id": job_id,
                    "actor_id": actor_id,
                    "apify_run_id": apify_run_id,
                    "dataset_id": dataset_id,
                    "status": "running",
                })
            else:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:500]}"
                con.execute("""
                    UPDATE apify_jobs
                    SET status = 'failed', error = ?, completed_at = current_timestamp
                    WHERE job_id = ?
                """, [error_msg, job_id])

                results.append({
                    "job_id": job_id,
                    "actor_id": actor_id,
                    "status": "failed",
                    "error": error_msg,
                })

        except Exception as e:
            error_msg = str(e)
            con.execute("""
                UPDATE apify_jobs
                SET status = 'failed', error = ?, completed_at = current_timestamp
                WHERE job_id = ?
            """, [error_msg, job_id])

            results.append({
                "job_id": job_id,
                "actor_id": actor_id,
                "status": "failed",
                "error": error_msg,
            })

    # Update pipeline status
    all_failed = all(r["status"] == "failed" for r in results)
    pipeline_status = "failed" if all_failed else "running" if not all_failed else "dispatching"
    con.execute("""
        UPDATE pipeline_runs SET status = ? WHERE run_id = ?
    """, [pipeline_status, pipeline_run_id])

    client.close()
    con.close()

    print(json.dumps({
        "status": "dispatched",
        "pipeline_run_id": pipeline_run_id,
        "jobs": results,
        "total": len(results),
        "running": sum(1 for r in results if r["status"] == "running"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
    }, indent=2))


def poll(pipeline_run_id: str = None, job_id: str = None):
    """Poll Apify for current status of running jobs."""
    token = get_apify_token()
    con = duckdb.connect(str(DB_PATH))

    if job_id:
        where = "j.job_id = ?"
        params = [job_id]
    elif pipeline_run_id:
        where = "j.run_id = ? AND j.status IN ('running', 'dispatched')"
        params = [pipeline_run_id]
    else:
        where = "j.status IN ('running', 'dispatched')"
        params = []

    jobs = con.execute(f"""
        SELECT j.job_id, j.apify_run_id, j.actor_id, j.status, j.run_id
        FROM apify_jobs j
        WHERE {where}
    """, params).fetchall()

    if not jobs:
        print(json.dumps({"status": "no_running_jobs", "message": "No running jobs to poll."}))
        con.close()
        return

    client = httpx.Client(
        base_url=APIFY_API_BASE,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )

    results = []
    for jid, apify_run_id, actor_id, current_status, run_id in jobs:
        if not apify_run_id:
            results.append({"job_id": jid, "status": current_status, "note": "No Apify run ID"})
            continue

        try:
            resp = client.get(f"/actor-runs/{apify_run_id}")
            if resp.status_code == 200:
                run_data = resp.json().get("data", {})
                apify_status = run_data.get("status", "UNKNOWN")
                status_map = {
                    "READY": "pending",
                    "RUNNING": "running",
                    "SUCCEEDED": "succeeded",
                    "FAILED": "failed",
                    "ABORTING": "failed",
                    "ABORTED": "failed",
                    "TIMED-OUT": "failed",
                }
                new_status = status_map.get(apify_status, current_status)

                result = {
                    "job_id": jid,
                    "actor_id": actor_id,
                    "apify_run_id": apify_run_id,
                    "status": new_status,
                    "apify_status": apify_status,
                }

                if new_status == "succeeded":
                    result["dataset_id"] = run_data.get("defaultDatasetId")
                    result["usage"] = run_data.get("usage", {})
                    result["stats"] = run_data.get("stats", {})

                if new_status == "failed":
                    result["error"] = run_data.get("statusMessage", "Unknown error")

                # Update DuckDB
                if new_status != current_status:
                    dataset_id = result.get("dataset_id")
                    error = result.get("error")
                    con.execute("""
                        UPDATE apify_jobs
                        SET status = ?,
                            dataset_id = COALESCE(?, dataset_id),
                            error = COALESCE(?, error),
                            completed_at = CASE WHEN ? IN ('succeeded', 'failed')
                                THEN current_timestamp ELSE completed_at END
                        WHERE job_id = ?
                    """, [new_status, dataset_id, error, new_status, jid])

                results.append(result)

        except Exception as e:
            results.append({"job_id": jid, "status": "poll_error", "error": str(e)})

    # Check if pipeline run is complete
    if pipeline_run_id:
        remaining = con.execute("""
            SELECT COUNT(*) FROM apify_jobs
            WHERE run_id = ? AND status IN ('pending', 'dispatched', 'running')
        """, [pipeline_run_id]).fetchone()[0]

        if remaining == 0:
            any_failed = con.execute("""
                SELECT COUNT(*) > 0 FROM apify_jobs
                WHERE run_id = ? AND status = 'failed'
            """, [pipeline_run_id]).fetchone()[0]
            final_status = "failed" if any_failed else "complete"
            con.execute("""
                UPDATE pipeline_runs
                SET status = ?, completed_at = current_timestamp
                WHERE run_id = ?
            """, [final_status, pipeline_run_id])

    client.close()
    con.close()

    print(json.dumps({
        "jobs": results,
        "total": len(results),
        "succeeded": sum(1 for r in results if r.get("status") == "succeeded"),
        "running": sum(1 for r in results if r.get("status") == "running"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
    }, indent=2))


def status(pipeline_run_id: str):
    """Show full status of a pipeline run."""
    con = duckdb.connect(str(DB_PATH))

    run = con.execute("""
        SELECT run_id, session_id, user_request, status, estimated_cost,
               created_at, completed_at, summary
        FROM pipeline_runs WHERE run_id = ?
    """, [pipeline_run_id]).fetchone()

    if not run:
        print(json.dumps({"error": f"Pipeline run {pipeline_run_id} not found."}))
        con.close()
        return

    jobs = con.execute("""
        SELECT job_id, apify_run_id, actor_id, status, dataset_id,
               dispatched_at, completed_at, error
        FROM apify_jobs WHERE run_id = ?
        ORDER BY dispatched_at
    """, [pipeline_run_id]).fetchall()

    landed = con.execute("""
        SELECT id, job_id, destination, path, row_count, landed_at
        FROM landed_data WHERE run_id = ?
    """, [pipeline_run_id]).fetchall()

    con.close()

    print(json.dumps({
        "pipeline_run": {
            "run_id": run[0], "session_id": run[1], "user_request": run[2],
            "status": run[3], "estimated_cost": run[4],
            "created_at": str(run[5]), "completed_at": str(run[6]),
            "summary": run[7],
        },
        "jobs": [{
            "job_id": j[0], "apify_run_id": j[1], "actor_id": j[2],
            "status": j[3], "dataset_id": j[4],
            "dispatched_at": str(j[5]), "completed_at": str(j[6]),
            "error": j[7],
        } for j in jobs],
        "landed_data": [{
            "id": l[0], "job_id": l[1], "destination": l[2],
            "path": l[3], "row_count": l[4], "landed_at": str(l[5]),
        } for l in landed],
    }, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Apify actor run management")
    sub = parser.add_subparsers(dest="command", required=True)

    # dispatch
    dispatch_parser = sub.add_parser("dispatch", help="Dispatch actor runs from plan JSON")
    dispatch_parser.add_argument("--plan", required=True, help="Path to plan JSON file or inline JSON")

    # poll
    poll_parser = sub.add_parser("poll", help="Poll running jobs for status")
    poll_parser.add_argument("--run-id", help="Pipeline run ID to poll")
    poll_parser.add_argument("--job-id", help="Specific job ID to poll")

    # status
    status_parser = sub.add_parser("status", help="Show pipeline run status")
    status_parser.add_argument("run_id", help="Pipeline run ID")

    args = parser.parse_args()

    if args.command == "dispatch":
        plan_input = args.plan
        if os.path.isfile(plan_input):
            plan = json.loads(Path(plan_input).read_text(encoding="utf-8"))
        else:
            plan = json.loads(plan_input)
        dispatch(plan)

    elif args.command == "poll":
        poll(pipeline_run_id=args.run_id, job_id=args.job_id)

    elif args.command == "status":
        status(args.run_id)


if __name__ == "__main__":
    main()
