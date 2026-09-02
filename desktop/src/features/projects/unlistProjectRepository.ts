import { canDeleteProject } from "@/features/projects/projectDeletion";
import { buildProjectPatchTemplate } from "@/features/projects/projectRepositoryCreation";
import type { Project, Repository } from "@/features/projects/projectModels";
import { removeRepositoryFromProject } from "@/features/projects/projectModels";
import type { UserProfileLookup } from "@/features/profile/lib/identity";
import { publishOwnedAgentProjectAnnouncements } from "@/features/projects/projectOwnerControl";
import { publishProjectOwnerAnnouncement } from "@/shared/api/projectGit";
import { relayClient } from "@/shared/api/relayClient";
import { signRelayEvent } from "@/shared/api/tauri";
import type { RelayEvent } from "@/shared/api/types";
import {
  KIND_DELETION,
  KIND_PROJECT_ANNOUNCEMENT,
  KIND_REPO_ANNOUNCEMENT,
} from "@/shared/constants/kinds";
import { normalizePubkey } from "@/shared/lib/pubkey";
import { isUnsupportedProjectKindError } from "@/features/projects/projectCreation";

export type UnlistProjectRepositoryResult = {
  previousProjectId: string;
  project: Project;
  unannounced: boolean;
};

type FetchEventsInput = Parameters<(typeof relayClient)["fetchEvents"]>[0];

type UnlistDependencies = {
  fetchEvents: (filter: FetchEventsInput) => Promise<RelayEvent[]>;
  nowSeconds: () => number;
  publishOwnedAgentAnnouncements: typeof publishOwnedAgentProjectAnnouncements;
  publishOwnerAnnouncement: typeof publishProjectOwnerAnnouncement;
  publishEvent: (
    event: RelayEvent,
    timeoutMessage: string,
    failureMessage: string,
  ) => Promise<void>;
  signEvent: typeof signRelayEvent;
};

const defaultDependencies: UnlistDependencies = {
  fetchEvents: relayClient.fetchEvents.bind(relayClient),
  nowSeconds: () => Math.floor(Date.now() / 1_000),
  publishOwnedAgentAnnouncements: publishOwnedAgentProjectAnnouncements,
  publishOwnerAnnouncement: publishProjectOwnerAnnouncement,
  publishEvent: async (event, timeoutMessage, failureMessage) => {
    await relayClient.publishEvent(event, timeoutMessage, failureMessage);
  },
  signEvent: signRelayEvent,
};

/** Owner (or owner of the authoring agent) can unlist a grouped member repo. */
export function canUnlistProjectRepository(
  project: Pick<Project, "legacy" | "owner" | "repositoryAddresses">,
  repository: Pick<Repository, "repoAddress">,
  currentPubkey: string | undefined,
  profiles?: UserProfileLookup,
): boolean {
  if (project.legacy) return false;
  if (!canDeleteProject(project, currentPubkey, profiles)) return false;
  return project.repositoryAddresses.includes(repository.repoAddress);
}

/**
 * Same-owner member announcements become legacy "ghost" cards if we only
 * drop the project `a` tag. Unannounce those 30617 events. Never touch a
 * repository the project owner does not control.
 */
export function shouldUnannounceMemberRepository(
  project: Pick<Project, "owner">,
  repository: Pick<Repository, "owner">,
): boolean {
  return normalizePubkey(project.owner) === normalizePubkey(repository.owner);
}

export function unlistConfirmCopy(repositoryName: string): {
  description: string;
  title: string;
} {
  return {
    title: "Unlist from Buzz?",
    description: `Removes "${repositoryName}" from this project and from Buzz listings so it cannot linger as a ghost. GitHub and folders on this computer are not deleted. You can attach a GitHub URL again later.`,
  };
}

export function buildRepositoryUnannounceTemplate(
  repository: Pick<Repository, "name" | "repoAddress">,
  liveHead: Pick<RelayEvent, "created_at">,
  nowSeconds: number,
): {
  kind: number;
  content: string;
  createdAt: number;
  tags: string[][];
} {
  return {
    kind: KIND_DELETION,
    content: `Unlist repository ${repository.name}`,
    createdAt: Math.max(nowSeconds, liveHead.created_at + 1),
    tags: [["a", repository.repoAddress]],
  };
}

/** Drop a member from the live 30621 head. Preserves non-membership tags. */
export function buildUnlistProjectPatchFromHead({
  liveHead,
  ownerPubkey,
  repositoryAddress,
}: {
  liveHead: RelayEvent;
  ownerPubkey: string;
  repositoryAddress: string;
}) {
  const liveAddresses = liveHead.tags
    .filter((tag) => tag[0] === "a" && tag[1])
    .map((tag) => tag[1] as string);
  if (!liveAddresses.includes(repositoryAddress)) {
    throw new Error(
      "This repository is not a member of the project anymore. Refresh and try again.",
    );
  }
  return buildProjectPatchTemplate({
    liveHead,
    ownerPubkey,
    repositoryAddresses: liveAddresses.filter(
      (address) => address !== repositoryAddress,
    ),
  });
}

/** Detach from the project and unannounce same-owner 30617 ghosts. */
export async function unlistProjectRepository(
  {
    ownerControlAgentPubkey,
    project,
    repository,
  }: {
    ownerControlAgentPubkey?: string;
    project: Project;
    repository: Repository;
  },
  deps: Partial<UnlistDependencies> = {},
): Promise<UnlistProjectRepositoryResult> {
  const {
    fetchEvents,
    nowSeconds,
    publishOwnedAgentAnnouncements,
    publishOwnerAnnouncement,
    publishEvent,
    signEvent,
  } = { ...defaultDependencies, ...deps };

  if (project.legacy) {
    throw new Error(
      "Standalone repositories are removed with Delete project, not Unlist.",
    );
  }

  const targetOwner = project.owner.toLowerCase();
  const liveHeads = await fetchEvents({
    kinds: [KIND_PROJECT_ANNOUNCEMENT],
    authors: [targetOwner],
    "#d": [project.dtag],
    limit: 1,
  });
  const liveHead = liveHeads[0];
  if (!liveHead) {
    throw new Error(
      "Could not find this project on the relay. Refresh and try again.",
    );
  }
  if (liveHead.created_at > project.createdAt) {
    throw new Error(
      "This project was updated by another session while you were working. Refresh and try again.",
    );
  }

  const projectTemplate = buildUnlistProjectPatchFromHead({
    liveHead,
    ownerPubkey: targetOwner,
    repositoryAddress: repository.repoAddress,
  });
  const unannounce = shouldUnannounceMemberRepository(project, repository);
  const createdAt = Math.max(nowSeconds(), liveHead.created_at + 1);

  if (unannounce) {
    const repoHeads = await fetchEvents({
      kinds: [KIND_REPO_ANNOUNCEMENT],
      authors: [repository.owner.toLowerCase()],
      "#d": [repository.dtag],
      limit: 1,
    });
    const repoHead = repoHeads[0];
    if (repoHead) {
      const deletion = buildRepositoryUnannounceTemplate(
        repository,
        repoHead,
        nowSeconds(),
      );
      if (ownerControlAgentPubkey) {
        await publishOwnedAgentAnnouncements(ownerControlAgentPubkey, [
          deletion,
        ]);
      } else {
        const signed = await signEvent(deletion);
        await publishEvent(
          signed,
          "Could not confirm whether the repository listing was removed. Refresh and try again.",
          "Failed to unlist the repository announcement.",
        );
      }
    }
  }

  if (ownerControlAgentPubkey) {
    const events = await publishOwnedAgentAnnouncements(
      ownerControlAgentPubkey,
      [{ ...projectTemplate, createdAt }],
    );
    const projectEvent =
      events.find((event) => event.kind === KIND_PROJECT_ANNOUNCEMENT) ??
      events[0];
    if (!projectEvent) {
      throw new Error(
        "The owner agent updated the project but its response was incomplete. Refresh and try again.",
      );
    }
    return {
      previousProjectId: project.id,
      project: removeRepositoryFromProject(
        project,
        repository.repoAddress,
        projectEvent.created_at,
      ),
      unannounced: unannounce,
    };
  }

  try {
    const publication = await publishOwnerAnnouncement({
      ...projectTemplate,
      createdAt,
      targetOwner,
    });
    if (publication.publicationError) {
      throw new Error(publication.publicationError);
    }
    return {
      previousProjectId: project.id,
      project: removeRepositoryFromProject(
        project,
        repository.repoAddress,
        publication.event.created_at,
      ),
      unannounced: unannounce,
    };
  } catch (error) {
    if (isUnsupportedProjectKindError(error)) {
      throw new Error(
        `This relay does not support multi-repository projects (event kind ${KIND_PROJECT_ANNOUNCEMENT}).`,
      );
    }
    throw error;
  }
}
