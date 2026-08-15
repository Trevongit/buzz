import { useQuery } from "@tanstack/react-query";

import { fetchGithubOpenPulls } from "./githubPulls";
import { parseGithubHttpsRepo } from "./githubRepo";

export function useGithubOpenPullsQuery(cloneUrl: string | null | undefined) {
  const parsed = parseGithubHttpsRepo(cloneUrl);
  return useQuery({
    enabled: Boolean(parsed),
    queryFn: () => fetchGithubOpenPulls(cloneUrl),
    queryKey: ["projects", "github-open-pulls", parsed?.owner, parsed?.repo],
    staleTime: 60_000,
  });
}
