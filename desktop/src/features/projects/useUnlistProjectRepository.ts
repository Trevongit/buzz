import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { Project, Repository } from "@/features/projects/hooks";
import { projectsQueryKey } from "@/features/projects/projectDeletionMutation";
import { markProjectDataAuthoritative } from "@/features/projects/projectSnapshot";
import {
  unlistProjectRepository,
  type UnlistProjectRepositoryResult,
} from "@/features/projects/unlistProjectRepository";

export function useUnlistProjectRepositoryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      ownerControlAgentPubkey?: string;
      project: Project;
      repository: Repository;
    }) => unlistProjectRepository(input),
    onSuccess: (result: UnlistProjectRepositoryResult) => {
      markProjectDataAuthoritative(result.project, "local-write");
      queryClient.setQueryData<Project[]>(projectsQueryKey, (current = []) =>
        current.map((item) =>
          item.id === result.previousProjectId ? result.project : item,
        ),
      );
    },
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: projectsQueryKey }),
  });
}
