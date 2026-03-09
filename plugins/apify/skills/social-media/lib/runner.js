#!/usr/bin/env node
/**
 * Start an Apify run, poll until complete, download dataset, save to disk.
 * Usage: node runner.js <actor_id> '<input_json>'
 * Outputs summary JSON to stdout.
 */

const { startRun, getRunStatus, getDatasetItems } = require("./api");
const dataWriter = require("./data-writer");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getPollingInterval(elapsedMs) {
  if (elapsedMs < 5 * 60 * 1000) return 30 * 1000;     // 0-5 min: 30s
  if (elapsedMs < 20 * 60 * 1000) return 60 * 1000;     // 5-20 min: 60s
  return 300 * 1000;                                      // 20+ min: 5m
}

async function main() {
  const actorId = process.argv[2];
  const inputJson = process.argv[3];

  if (!actorId || !inputJson) {
    console.error("Usage: node runner.js <actor_id> '<input_json>'");
    process.exit(1);
  }

  let input;
  try {
    input = JSON.parse(inputJson);
  } catch (e) {
    console.error(JSON.stringify({ error: "Invalid input JSON: " + e.message }));
    process.exit(1);
  }

  try {
    // Start the run
    const run = await startRun(actorId, input);
    const runId = run.data.id;
    const startTime = Date.now();

    process.stderr.write("Run started: " + runId + "\n");

    // Poll until terminal status
    let status;
    while (true) {
      const elapsed = Date.now() - startTime;
      const interval = getPollingInterval(elapsed);
      await sleep(interval);

      const runData = await getRunStatus(runId);
      status = runData.data.status;
      process.stderr.write("Status: " + status + " (" + Math.round(elapsed / 1000) + "s)\n");

      if (status === "SUCCEEDED" || status === "FAILED" || status === "ABORTED" || status === "TIMED-OUT") {
        break;
      }
    }

    if (status !== "SUCCEEDED") {
      console.log(JSON.stringify({
        run_id: runId,
        status: status,
        error: "Run did not succeed: " + status,
      }));
      process.exit(1);
    }

    // Get the dataset
    const runData = await getRunStatus(runId);
    const datasetId = runData.data.defaultDatasetId;

    if (!datasetId) {
      console.log(JSON.stringify({
        run_id: runId,
        status: status,
        error: "No dataset ID found",
      }));
      process.exit(1);
    }

    const items = await getDatasetItems(datasetId);

    // Write to disk and get summary
    const summary = dataWriter.write(runId, items);
    console.log(JSON.stringify(summary));

  } catch (err) {
    console.error(JSON.stringify({ error: err.message }));
    process.exit(1);
  }
}

main();
