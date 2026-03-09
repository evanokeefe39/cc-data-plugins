#!/usr/bin/env node
/**
 * Write Apify dataset to disk and return summary.
 * Can be used as a module (require) or standalone (stdin).
 *
 * Module usage: const { write } = require("./data-writer"); write(runId, items);
 * Standalone:  echo '<json>' | node data-writer.js <run_id>
 */

const fs = require("fs");
const path = require("path");

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function ensureGitignore() {
  const gitignorePath = path.join(process.cwd(), ".gitignore");
  if (fs.existsSync(gitignorePath)) {
    const content = fs.readFileSync(gitignorePath, "utf8");
    if (content.includes(".apify/")) return;
  }
  fs.appendFileSync(gitignorePath, "\n.apify/\n");
}

function write(runId, items) {
  const dataArray = Array.isArray(items) ? items : (items.data || items);
  const dataDir = path.join(process.cwd(), ".apify", "data", runId);
  ensureDir(dataDir);

  // Write raw data
  const rawPath = path.join(dataDir, "raw.json");
  const rawContent = JSON.stringify(dataArray, null, 2);
  fs.writeFileSync(rawPath, rawContent);

  // Build summary
  const rowCount = dataArray.length;
  const fields = rowCount > 0 ? Object.keys(dataArray[0]) : [];
  const sampleRows = dataArray.slice(0, 3);
  const fileSizeBytes = Buffer.byteLength(rawContent);
  const fileSize = fileSizeBytes > 1024 * 1024
    ? (fileSizeBytes / (1024 * 1024)).toFixed(1) + " MB"
    : (fileSizeBytes / 1024).toFixed(1) + " KB";

  const summary = {
    run_id: runId,
    row_count: rowCount,
    fields: fields,
    sample_rows: sampleRows,
    file_path: ".apify/data/" + runId + "/raw.json",
    file_size: fileSize,
  };

  // Write summary
  const summaryPath = path.join(dataDir, "summary.json");
  fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2));

  // Ensure gitignore
  ensureGitignore();

  return summary;
}

// Standalone mode: read from stdin
if (require.main === module) {
  const runId = process.argv[2];
  if (!runId) {
    console.error("Usage: echo '<json>' | node data-writer.js <run_id>");
    process.exit(1);
  }

  let input = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => { input += chunk; });
  process.stdin.on("end", () => {
    try {
      const items = JSON.parse(input);
      const summary = write(runId, items);
      console.log(JSON.stringify(summary));
    } catch (err) {
      console.error(JSON.stringify({ error: err.message }));
      process.exit(1);
    }
  });
}

module.exports = { write };
