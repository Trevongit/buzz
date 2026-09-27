import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const manifest = JSON.parse(
  readFileSync(
    new URL("../../../../preview-features.json", import.meta.url),
    "utf8",
  ),
);

test("spelling suggestions is a default-off desktop experiment", () => {
  const feature = manifest.features.find(
    ({ id }) => id === "composerSpellcheck",
  );

  assert.equal(feature.name, "Spelling suggestions");
  assert.deepEqual(feature.platforms, ["desktop"]);
  assert.equal(feature.defaultEnabled, undefined);
});

test("jev doorman is a default-off desktop experiment and does not mention Agents keys", () => {
  const feature = manifest.features.find(({ id }) => id === "jevDoorman");

  assert.deepEqual(feature, {
    id: "jevDoorman",
    name: "Jev doorman",
    description:
      "Cheap yes/no before waking a chair: need act, which mouth, public vs private. Opt-in. Does not store a TypeSafe key on the Agents page. The caller stays extras on this computer (env file, not git).",
    platforms: ["desktop"],
  });
  assert.equal(feature.defaultEnabled, undefined);
  assert.equal(/nsec/i.test(feature.description), false);
});

test("existing Projects and Workflows experiments remain unchanged", () => {
  const existing = Object.fromEntries(
    manifest.features
      .filter(({ id }) => id === "projects" || id === "workflows")
      .map((feature) => [feature.id, feature]),
  );

  assert.deepEqual(existing, {
    projects: {
      id: "projects",
      name: "Projects",
      description: "Git repository browser and collaboration",
      platforms: ["desktop"],
    },
    workflows: {
      id: "workflows",
      name: "Workflows",
      description: "YAML-defined automations with approval gates",
      platforms: ["desktop"],
    },
  });
});
