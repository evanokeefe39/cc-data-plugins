#!/usr/bin/env node
/**
 * Fetch actor pricing and calculate cost estimate.
 * Usage: node cost.js <actor_id> <max_items>
 * Outputs JSON to stdout.
 */

const { getActorDetails } = require("./api");

/** Extract price from an event object. Handles both flat and tiered pricing. */
function getEventPrice(event) {
  if (!event) return null;
  // Flat price (older format)
  if (event.eventPriceUsd != null) return event.eventPriceUsd;
  // Tiered price (newer format) -- use FREE tier as conservative estimate
  if (event.eventTieredPricingUsd && event.eventTieredPricingUsd.FREE) {
    return event.eventTieredPricingUsd.FREE.tieredEventPriceUsd;
  }
  return null;
}

async function main() {
  const actorId = process.argv[2];
  const maxItems = parseInt(process.argv[3], 10) || 50;

  if (!actorId) {
    console.error("Usage: node cost.js <actor_id> <max_items>");
    process.exit(1);
  }

  try {
    const details = await getActorDetails(actorId);
    const pricingInfos = details.data && details.data.pricingInfos;
    // Use the most recent (last) pricing entry
    const pricing = Array.isArray(pricingInfos) && pricingInfos.length > 0
      ? pricingInfos[pricingInfos.length - 1]
      : null;

    let costPerItem = null;
    let startCost = null;
    let estimatedTotal = null;
    let pricingModel = "unknown";
    let note = null;

    if (pricing && pricing.pricingModel === "PAY_PER_EVENT") {
      pricingModel = "pay_per_event";
      const events = pricing.pricingPerEvent &&
        pricing.pricingPerEvent.actorChargeEvents;
      if (events) {
        // Find primary result event: isPrimaryEvent flag, or first non-start event
        const primaryEvent = Object.entries(events).find(
          ([, v]) => v.isPrimaryEvent
        );
        const fallbackEvent = Object.entries(events).find(
          ([k]) => k !== "actor-start"
        );
        const itemEvent = primaryEvent || fallbackEvent;
        if (itemEvent) costPerItem = getEventPrice(itemEvent[1]);
        startCost = getEventPrice(events["actor-start"]);
      }
      if (costPerItem) {
        estimatedTotal = Math.round(((startCost || 0) + costPerItem * maxItems) * 1000) / 1000;
      }
    } else if (pricing && pricing.pricingModel === "PAY_PER_RESULT") {
      pricingModel = "pay_per_result";
      costPerItem = pricing.pricePerResult || null;
      if (costPerItem) {
        estimatedTotal = Math.round(costPerItem * maxItems * 100) / 100;
      }
    } else if (pricing && pricing.pricingModel === "PRICE_PER_DATASET_ITEM") {
      pricingModel = "pay_per_result";
      costPerItem = pricing.pricePerDatasetItem || null;
      // Handle tiered pricing (newer format)
      if (!costPerItem && pricing.tieredPricing && pricing.tieredPricing.FREE) {
        costPerItem = pricing.tieredPricing.FREE.tieredPricePerUnitUsd;
      }
      if (costPerItem) {
        estimatedTotal = Math.round(costPerItem * maxItems * 1000) / 1000;
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
    if (startCost) result.start_cost = startCost;
    if (note) result.note = note;

    console.log(JSON.stringify(result));
  } catch (err) {
    console.error(JSON.stringify({ error: err.message }));
    process.exit(1);
  }
}

main();
