import { useQueries } from "@tanstack/react-query";
import { useFeatureEnabled } from "@/shared/features";

import type {
  ProjectRepoSnapshot,
  Repository,
} from "@/features/projects/hooks";
import { fetchRepoState } from "@/features/projects/hooks";
import { resolveProjectDefaultBranch } from "@/features/projects/lib/projectBranches";
import {
  getProjectRepoSnapshot,
  githubRemoteReadsEnabled,
  isGithubCloneUrl,
} from "@/shared/api/projectGit";

export type ProjectRepositorySnapshotResult = {
  error: unknown;
  isLoading: boolean;
  repository: Repository;
  snapshot: ProjectRepoSnapshot | null;
};

/** Loads each project repository independently so one failure stays partial. */
export function useProjectRepositorySnapshots(
  repositories: Repository[],
  enabled = true,
): ProjectRepositorySnapshotResult[] {
  const publicGithubRead = useFeatureEnabled("publicGithubRead");
  const githubMachineGit = useFeatureEnabled("githubMachineGit");
  const githubReads = publicGithubRead || githubMachineGit;
  const queries = useQueries({
    queries: repositories.map((repository) => ({
      enabled: Boolean(
        enabled &&
          repository.cloneUrls[0] &&
          (!isGithubCloneUrl(repository.cloneUrls[0]) || githubReads),
      ),
      queryFn: async () => {
        const cloneUrl = repository.cloneUrls[0];
        if (!cloneUrl) return null;
        if (isGithubCloneUrl(cloneUrl) && !githubRemoteReadsEnabled()) {
          return null;
        }
        const repoState = await fetchRepoState(repository);
        const defaultBranch = resolveProjectDefaultBranch(
          repository.defaultBranch,
          repoState,
        );
        return getProjectRepoSnapshot({
          baseBranch: defaultBranch,
          cloneUrl,
          defaultBranch,
        });
      },
      queryKey: [
        "project",
        repository.id,
        "repo-snapshot",
        repository.defaultBranch,
        "none",
        "none",
        "no-tag",
        "no-tag-commit",
        githubReads,
      ],
      retry: 1,
      staleTime: 30_000,
    })),
  });

  return repositories.map((repository, index) => {
    const query = queries[index];
    return {
      error:
        enabled && !repository.cloneUrls[0]
          ? new Error("Repository not found on the relay.")
          : query?.error,
      isLoading: query?.isLoading ?? false,
      repository,
      snapshot: query?.data ?? null,
    };
  });
}
