import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";

import { OVERRIDES_KEY } from "./store.ts";
import { previewFeatureEnabled } from "./previewFeature.ts";

function installStorage(value) {
  const values = new Map([
    [OVERRIDES_KEY, value === undefined ? undefined : JSON.stringify(value)],
  ]);
  globalThis.window = {
    localStorage: {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, next) => {
        values.set(key, String(next));
      },
    },
  };
}

afterEach(() => {
  delete globalThis.window;
});

describe("previewFeatureEnabled", () => {
  it("defaults Pocket Listen on when there is no override", () => {
    installStorage({});
    assert.equal(previewFeatureEnabled("pocketListen"), true);
  });

  it("defaults public GitHub reads on when there is no override", () => {
    installStorage({});
    assert.equal(previewFeatureEnabled("publicGithubRead"), true);
  });

  it("defaults GitHub machine git off when there is no override", () => {
    installStorage({});
    assert.equal(previewFeatureEnabled("githubMachineGit"), false);
  });

  it("lets an explicit opt-out hide a default-on extra", () => {
    installStorage({ pocketListen: false, publicGithubRead: false });
    assert.equal(previewFeatureEnabled("pocketListen"), false);
    assert.equal(previewFeatureEnabled("publicGithubRead"), false);
  });

  it("fail-opens unknown ids so graduation stays always-on", () => {
    installStorage({});
    assert.equal(previewFeatureEnabled("graduated-extra"), true);
  });
});
