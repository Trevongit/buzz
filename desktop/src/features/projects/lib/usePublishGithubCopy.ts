import * as React from "react";
import { toast } from "sonner";

import { deriveRelayCloneUrl } from "@/features/projects/lib/projectCloneUrl";
import { parseGithubHttpsRepo } from "@/features/projects/lib/githubRepo";
import { publishGithubRepoToBuzz } from "@/shared/api/projectGit";

type PublishableRepository = {
  cloneUrls: string[];
  dtag: string;
  owner: string;
};

export function usePublishGithubCopy({
  onPublished,
  relayOrigin,
  repository,
  viewerPubkey,
}: {
  onPublished?: () => void | Promise<void>;
  relayOrigin: string | null | undefined;
  repository: PublishableRepository | null | undefined;
  viewerPubkey: string | null | undefined;
}) {
  const [pending, setPending] = React.useState(false);
  const destCloneUrl = repository
    ? deriveRelayCloneUrl(relayOrigin, repository.owner, repository.dtag)
    : null;
  const canPublish = Boolean(
    repository &&
      parseGithubHttpsRepo(repository.cloneUrls[0]) &&
      viewerPubkey &&
      viewerPubkey.toLowerCase() === repository.owner.toLowerCase() &&
      destCloneUrl,
  );

  const publish = React.useCallback(async () => {
    const githubCloneUrl = repository?.cloneUrls[0];
    if (!repository || !parseGithubHttpsRepo(githubCloneUrl) || !destCloneUrl) {
      return;
    }
    setPending(true);
    try {
      const result = await publishGithubRepoToBuzz({
        destCloneUrl,
        githubCloneUrl,
      });
      toast.success(result.message, { description: result.destCloneUrl });
      await onPublished?.();
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to publish a copy to this relay.",
      );
    } finally {
      setPending(false);
    }
  }, [destCloneUrl, onPublished, repository]);

  return { canPublish, pending, publish };
}
