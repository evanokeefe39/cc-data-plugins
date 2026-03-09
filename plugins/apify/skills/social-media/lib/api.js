/**
 * Apify REST API client.
 * Reads APIFY_API_TOKEN from .env at plugin root.
 */

const fs = require("fs");
const path = require("path");

const BASE_URL = "https://api.apify.com/v2";

function loadToken() {
  const envPath = path.join(process.cwd(), ".env");
  if (!fs.existsSync(envPath)) {
    throw new Error(
      "Missing .env file in project directory (" + envPath + ")\n" +
      "Create it with: APIFY_API_TOKEN=apify_api_xxx"
    );
  }
  const content = fs.readFileSync(envPath, "utf8");
  const match = content.match(/^APIFY_API_TOKEN=(.+)$/m);
  if (!match || !match[1].trim()) {
    throw new Error("APIFY_API_TOKEN not found in .env file");
  }
  return match[1].trim();
}

const TOKEN = loadToken();

async function apiFetch(endpoint, options = {}) {
  const url = BASE_URL + endpoint;
  const headers = {
    Authorization: "Bearer " + TOKEN,
    "Content-Type": "application/json",
    ...options.headers,
  };
  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error("Apify API " + res.status + ": " + body.slice(0, 500));
  }
  return res.json();
}

async function getActorDetails(actorId) {
  return apiFetch("/acts/" + encodeURIComponent(actorId));
}

async function startRun(actorId, input) {
  return apiFetch("/acts/" + encodeURIComponent(actorId) + "/runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

async function getRunStatus(runId) {
  return apiFetch("/actor-runs/" + runId);
}

async function getDatasetItems(datasetId, opts = {}) {
  const limit = opts.limit || 1000;
  return apiFetch("/datasets/" + datasetId + "/items?limit=" + limit);
}

module.exports = { getActorDetails, startRun, getRunStatus, getDatasetItems };
