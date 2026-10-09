#!/usr/bin/env node
// Reproduce row=none vs 💬 bug
// Simulate heldEmojiFor logic before fix

const EMOJI_HOLD_MS = 5000;
const AGENT_EMOJI = "💬";
const BASH_EMOJI = "🖥️";

function simulateOldLogic({ live, speaking, heldEmoji, heldEmojiAt, now, strongRowExists }) {
  const speechFresh = speaking || (live && heldEmoji === AGENT_EMOJI && now - heldEmojiAt < EMOJI_HOLD_MS);
  let row = live && !speechFresh ? (strongRowExists ? { label: "bash running" } : null) : null;
  let emoji = live && row ? BASH_EMOJI : null;
  if (!emoji && speechFresh) {
    emoji = AGENT_EMOJI;
  }
  return { speechFresh, row, emoji };
}

function simulateNewLogic({ live, speaking, heldEmoji, heldEmojiAt, now, strongRowExists }) {
  const speechHold = live && heldEmoji === AGENT_EMOJI && now - heldEmojiAt < EMOJI_HOLD_MS;
  // If speaking now, speech wins
  if (speaking) {
    return { emoji: AGENT_EMOJI, reason: "speaking" };
  }
  // Check action rows first
  let row = live && strongRowExists ? { label: "bash running" } : null;
  let emoji = row ? BASH_EMOJI : null;
  if (emoji) {
    return { emoji, reason: "action row" };
  }
  // No action row, but hold active
  if (speechHold) {
    return { emoji: AGENT_EMOJI, reason: "hold" };
  }
  return { emoji: null, reason: "none" };
}

const now = Date.now();
const scenario = {
  live: true,
  speaking: false, // no new word, just hold
  heldEmoji: AGENT_EMOJI,
  heldEmojiAt: now - 1000, // 1s ago, within hold
  now: now,
  strongRowExists: true, // there IS an action row
};

const oldResult = simulateOldLogic(scenario);
const newResult = simulateNewLogic(scenario);

console.log("Scenario: live=true, speaking=false, held=💬 (hold active 1s ago), strongRow exists=true");
console.log("Old logic:", oldResult);
console.log("New logic:", newResult);

if (oldResult.emoji === AGENT_EMOJI && oldResult.row === null) {
  console.log("BUG REPRODUCED: old logic returns 💬 with row=null, overriding action row");
} else {
  console.log("Bug NOT reproduced with old logic");
}

if (newResult.emoji === BASH_EMOJI) {
  console.log("FIX VERIFIED: new logic returns action row emoji 🖥️ instead of 💬");
} else {
  console.log("Fix FAILED: new logic still returns", newResult.emoji);
}

// Also test speaking case: speaking should win over action row
const speakingScenario = {
  live: true,
  speaking: true,
  heldEmoji: AGENT_EMOJI,
  heldEmojiAt: now - 1000,
  now: now,
  strongRowExists: true,
};
const newSpeaking = simulateNewLogic(speakingScenario);
console.log("\nSpeaking scenario: speaking=true, strongRow=true");
console.log("New logic should return 💬 (speaking wins):", newSpeaking);
if (newSpeaking.emoji === AGENT_EMOJI) {
  console.log("Speaking priority OK");
} else {
  console.log("Speaking priority WRONG");
}
