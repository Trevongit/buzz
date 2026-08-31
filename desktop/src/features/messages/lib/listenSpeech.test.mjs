import assert from "node:assert/strict";
import { test } from "node:test";

import {
  finishSpokenSummary,
  isFollowAlongMessage,
  isReaderAgentName,
  listenPlainText,
  listenReaderAsk,
  listenSummaryPrompt,
  spokenProseFromReaderReply,
} from "./listenSpeech.ts";

test("strips markdown into speakable prose", () => {
  assert.equal(
    listenPlainText("**Ship** [extras](https://example.com) tonight."),
    "Ship extras tonight.",
  );
});

test("drops fenced code and images", () => {
  assert.equal(
    listenPlainText("See this.\n```rs\nfn main() {}\n```\n![shot](a.png)"),
    "See this.",
  );
});

test("summary prompt keeps the source text", () => {
  const prompt = listenSummaryPrompt("Need git 2.46.");
  assert.match(prompt, /spoken prose/);
  assert.match(prompt, /Need git 2.46\./);
  assert.match(prompt, /finish the last sentence/);
});

test("finishSpokenSummary drops a cut-off trailing clause", () => {
  assert.equal(
    finishSpokenSummary(
      "Origin stays the trunk. Extras is a module pack on top. Listen uses Pocket TTS and then the rewrite was",
    ),
    "Origin stays the trunk. Extras is a module pack on top.",
  );
});

test("finishSpokenSummary keeps a complete last sentence", () => {
  assert.equal(
    finishSpokenSummary("Keep names, decisions, and numbers."),
    "Keep names, decisions, and numbers.",
  );
});

test("isReaderAgentName matches Reader-laptop", () => {
  assert.equal(isReaderAgentName("Reader-laptop"), true);
  assert.equal(isReaderAgentName("reader laptop"), true);
  assert.equal(isReaderAgentName("Buzz-grok"), false);
});

test("isFollowAlongMessage matches Reader posts and read-along agent bodies", () => {
  assert.equal(
    isFollowAlongMessage({ author: "Reader-laptop", body: "Hello." }),
    true,
  );
  assert.equal(
    isFollowAlongMessage({
      author: "unknown",
      body: "Spoken\nHello.\n\nRead-along\n- one",
      isAgent: true,
    }),
    true,
  );
  assert.equal(
    isFollowAlongMessage({ author: "open121", body: "hello", isAgent: false }),
    false,
  );
});

test("listenReaderAsk mentions the chosen agent", () => {
  assert.match(
    listenReaderAsk("Reader-laptop", "Ship extras tonight."),
    /@Reader-laptop/,
  );
  assert.match(listenReaderAsk("Knowing", "Ship extras tonight."), /@Knowing/);
  assert.match(
    listenReaderAsk("Reader-laptop", "Ship extras tonight."),
    /Ship extras tonight/,
  );
  assert.match(
    listenReaderAsk("Reader-laptop", "Ship extras tonight."),
    /read-along/,
  );
  assert.match(
    listenReaderAsk("Reader-laptop", "Ship extras tonight."),
    /diagrams/,
  );
});

test("isFollowAlongMessage matches a preferred Listen-summary agent", () => {
  assert.equal(
    isFollowAlongMessage(
      { author: "Knowing", body: "Spoken\nHello." },
      "Knowing",
    ),
    true,
  );
});

test("spokenProseFromReaderReply prefers the Spoken section", () => {
  const reply = `Spoken
Origin stays the trunk. Extras is a module pack.

Read-along
- Keep one extras branch`;
  assert.equal(
    spokenProseFromReaderReply(reply),
    "Origin stays the trunk. Extras is a module pack.",
  );
});
