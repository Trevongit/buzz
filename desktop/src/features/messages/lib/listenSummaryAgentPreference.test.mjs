import assert from "node:assert/strict";
import { test } from "node:test";

import {
  pickListenSummaryAgent,
  resetListenSummaryAgentPreferenceForTests,
  writeListenSummaryAgentPreference,
} from "./listenSummaryAgentPreference.ts";

test("pickListenSummaryAgent prefers in-memory preference, else Reader-laptop", () => {
  resetListenSummaryAgentPreferenceForTests();
  const agents = [
    { name: "Knowing", pubkey: "aaa" },
    { name: "Reader-laptop", pubkey: "bbb" },
  ];
  assert.equal(pickListenSummaryAgent(agents)?.pubkey, "bbb");
  writeListenSummaryAgentPreference({ name: "Knowing", pubkey: "aaa" });
  assert.equal(pickListenSummaryAgent(agents)?.name, "Knowing");
  resetListenSummaryAgentPreferenceForTests();
});
