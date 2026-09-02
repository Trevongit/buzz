import assert from "node:assert/strict";
import test from "node:test";

import {
  buildRepositoryUnannounceTemplate,
  buildUnlistProjectPatchFromHead,
  canUnlistProjectRepository,
  shouldUnannounceMemberRepository,
  unlistConfirmCopy,
  unlistProjectRepository,
} from "./unlistProjectRepository.ts";

const OWNER = "a".repeat(64);
const OTHER = "b".repeat(64);
const REPO = `30617:${OWNER}:ai-backup-librarian`;
const GITHUB = `30617:${OWNER}:ai-backup-librarian-github`;
const CHANNEL = "11111111-1111-4111-8111-111111111111";

const project = {
  createdAt: 50,
  description: "",
  dtag: "ai-backup-librarian",
  id: `30621:${OWNER}:ai-backup-librarian`,
  legacy: false,
  name: "AI Backup Librarian",
  owner: OWNER,
  primaryRepositoryAddress: REPO,
  projectAddress: `30621:${OWNER}:ai-backup-librarian`,
  projectChannelId: CHANNEL,
  repositories: [],
  repositoryAddresses: [REPO, GITHUB],
  status: "active",
};

const repository = {
  createdAt: 40,
  description: "",
  dtag: "ai-backup-librarian",
  id: `${OWNER}:ai-backup-librarian`,
  name: "AI Backup Librarian",
  owner: OWNER,
  repoAddress: REPO,
};

function projectHead(overrides = {}) {
  return {
    id: "1".repeat(64),
    kind: 30621,
    pubkey: OWNER,
    created_at: 50,
    content: "",
    tags: [
      ["d", "ai-backup-librarian"],
      ["name", "AI Backup Librarian"],
      ["buzz-channel", CHANNEL],
      ["future", "keep"],
      ["a", REPO],
      ["a", GITHUB],
    ],
    ...overrides,
  };
}

test("canUnlistProjectRepository is owner-only on grouped members", () => {
  assert.equal(canUnlistProjectRepository(project, repository, OWNER), true);
  assert.equal(canUnlistProjectRepository(project, repository, OTHER), false);
  assert.equal(
    canUnlistProjectRepository({ ...project, legacy: true }, repository, OWNER),
    false,
  );
});

test("shouldUnannounceMemberRepository only when the project owner signed the 30617", () => {
  assert.equal(shouldUnannounceMemberRepository(project, repository), true);
  assert.equal(
    shouldUnannounceMemberRepository(project, { ...repository, owner: OTHER }),
    false,
  );
});

test("unlist confirm copy never claims GitHub or disk deletion", () => {
  const copy = unlistConfirmCopy("AI Backup Librarian");
  assert.match(copy.title, /Unlist from Buzz/);
  assert.match(copy.description, /not deleted/);
  assert.match(copy.description, /folders on this computer are not deleted/);
  assert.doesNotMatch(copy.description, /permanently delete GitHub/i);
});

test("buildUnlistProjectPatchFromHead drops only the target member and keeps extension tags", () => {
  const template = buildUnlistProjectPatchFromHead({
    liveHead: projectHead(),
    ownerPubkey: OWNER,
    repositoryAddress: REPO,
  });
  assert.equal(template.kind, 30621);
  assert.deepEqual(
    template.tags.filter((tag) => tag[0] === "a"),
    [["a", GITHUB]],
  );
  assert.deepEqual(
    template.tags.find((tag) => tag[0] === "future"),
    ["future", "keep"],
  );
});

test("buildRepositoryUnannounceTemplate is an a-tag-only kind:5", () => {
  const template = buildRepositoryUnannounceTemplate(
    repository,
    { created_at: 40 },
    39,
  );
  assert.equal(template.kind, 5);
  assert.deepEqual(template.tags, [["a", REPO]]);
  assert.equal(template.createdAt, 41);
});

test("unlistProjectRepository tombstones same-owner 30617 then patches 30621", async () => {
  const calls = [];
  const result = await unlistProjectRepository(
    { project, repository },
    {
      fetchEvents: async (filter) => {
        calls.push(["fetch", filter]);
        if (filter.kinds?.includes(30621)) return [projectHead()];
        return [
          {
            id: "2".repeat(64),
            kind: 30617,
            pubkey: OWNER,
            created_at: 40,
            content: "",
            tags: [["d", "ai-backup-librarian"]],
          },
        ];
      },
      nowSeconds: () => 80,
      signEvent: async (template) => {
        calls.push(["sign", template]);
        return {
          id: "3".repeat(64),
          kind: template.kind,
          pubkey: OWNER,
          created_at: template.createdAt,
          content: template.content,
          tags: template.tags,
        };
      },
      publishEvent: async (event) => {
        calls.push(["publishDeletion", event.kind, event.tags]);
      },
      publishOwnerAnnouncement: async (input) => {
        calls.push(["publishProject", input.kind, input.tags]);
        return {
          event: {
            id: "4".repeat(64),
            kind: 30621,
            pubkey: OWNER,
            created_at: input.createdAt ?? 81,
            content: input.content,
            tags: input.tags,
          },
          publicationError: null,
        };
      },
    },
  );

  assert.equal(result.unannounced, true);
  assert.deepEqual(result.project.repositoryAddresses, [GITHUB]);
  assert.equal(calls.find((call) => call[0] === "publishDeletion")?.[1], 5);
  const projectPublish = calls.find((call) => call[0] === "publishProject");
  assert.deepEqual(
    projectPublish[2].filter((tag) => tag[0] === "a"),
    [["a", GITHUB]],
  );
});

test("unlistProjectRepository does not unannounce a foreign member", async () => {
  const calls = [];
  const foreign = {
    ...repository,
    owner: OTHER,
    repoAddress: `30617:${OTHER}:other`,
  };
  const grouped = {
    ...project,
    repositoryAddresses: [`30617:${OTHER}:other`, GITHUB],
  };
  await unlistProjectRepository(
    { project: grouped, repository: foreign },
    {
      fetchEvents: async () => [
        projectHead({
          tags: [
            ["d", "ai-backup-librarian"],
            ["name", "AI Backup Librarian"],
            ["buzz-channel", CHANNEL],
            ["a", `30617:${OTHER}:other`],
            ["a", GITHUB],
          ],
        }),
      ],
      nowSeconds: () => 80,
      signEvent: async () => {
        throw new Error("must not sign a foreign unannounce");
      },
      publishEvent: async () => {
        throw new Error("must not publish a foreign unannounce");
      },
      publishOwnerAnnouncement: async (input) => {
        calls.push(input.tags.filter((tag) => tag[0] === "a"));
        return {
          event: {
            id: "4".repeat(64),
            kind: 30621,
            pubkey: OWNER,
            created_at: 81,
            content: "",
            tags: input.tags,
          },
          publicationError: null,
        };
      },
    },
  );
  assert.deepEqual(calls[0], [["a", GITHUB]]);
});
