#!/usr/bin/env node
/**
 * Fetch actor pricing and calculate cost estimate.
 * Usage: node cost.js <actor_id> <max_items>
 * Outputs JSON to stdout.
 */

const { getActorDetails } = require("./api");

async function main() {
  const actorId = process.argv[2];
  const maxItems = parseInt(process.argv[3], 10) || 50;

  if (!actorId) {
    console.error("Usage: node cost.js <actor_id> <max_items>");
    process.exit(1);
  }

  try {
    const details = await getActorDetails(actorId);
    const pricing = details.data && details.data.pricingInfo;

    let costPerItem = null;
    let estimatedTotal = null;
    let pricingModel = "unknown";
    let note = null;

    if (pricing && pricing.pricingModel === "PAY_PER_RESULT") {
      pricingModel = "pay_per_result";
      costPerItem = pricing.pricePerResult || null;
      if (costPerItem) {
        estimatedTotal = Math.round(costPerItem * maxItems * 100) / 100;
      }
    } else if (pricing && pricing.pricingModel === "PRICE_PER_DATASET_ITEM") {
      pricingModel = "pay_per_result";
      costPerItem = pricing.pricePerDatasetItem || null;
      if (costPerItem) {
        estimatedTotal = Math.round(costPerItem * maxItems * 100) / 100;
      }
    } else if (pricing) {
      pricingModel = pricing.pricingModel || "unknown";
      note = "cost unknown -- check Apify console for pricing";
    } else {
      note = "cost unknown -- no pricing info returned";
    }

    const result = {
      actor_id: actorId,
      actor_name: details.data && details.data.title,
      pricing_model: pricingModel,
      cost_per_item: costPerItem,
      estimated_total: estimatedTotal,
      max_items: maxItems,
    };
    if (note) result.note = note;

    console.log(JSON.stringify(result));
  } catch (err) {
    console.error(JSON.stringify({ error: err.message }));
    process.exit(1);
  }
}

main();
