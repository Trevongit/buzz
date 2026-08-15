import { ExternalLink, GitBranch } from "lucide-react";

import type { GithubPullSummary } from "@/features/projects/lib/githubPulls";
import { parseGithubHttpsRepo } from "@/features/projects/lib/githubRepo";
import {
  formatExactTimestamp,
  relativeTime,
} from "@/features/projects/lib/projectsViewHelpers";
import { useGithubOpenPullsQuery } from "@/features/projects/lib/useGithubOpenPulls";
import { GitHubMark } from "./GitHubMark";
import { ProjectFeedRow, ProjectFeedRowCluster } from "./ProjectFeedRow";

function GithubPullRequestRow({ pull }: { pull: GithubPullSummary }) {
  return (
    <ProjectFeedRow
      meta={
        <>
          <span className="truncate">
            {pull.userLogin} opened on GitHub{" "}
            <span title={formatExactTimestamp(pull.createdAt)}>
              {relativeTime(pull.createdAt)}
            </span>
          </span>
          {pull.headRef && pull.baseRef ? (
            <span className="inline-flex min-w-0 items-center gap-1 rounded-full border border-border/60 px-1.5 py-0.5 font-mono text-2xs">
              <GitBranch className="h-3 w-3 shrink-0" />
              <span className="truncate">
                {pull.headRef} → {pull.baseRef}
              </span>
            </span>
          ) : null}
          <span className="rounded-full border border-border/60 px-1.5 py-0.5 text-2xs font-medium text-muted-foreground">
            {pull.draft ? "Draft" : "Open"}
          </span>
        </>
      }
      onOpen={() => {
        window.open(pull.htmlUrl, "_blank", "noopener,noreferrer");
      }}
      statusIcon={<GitHubMark className="h-3.5 w-3.5 shrink-0" />}
      testId="github-pull-request-row"
      title={`#${pull.number} ${pull.title}`}
      trailing={
        <ProjectFeedRowCluster>
          <a
            aria-label={`Open GitHub pull request #${pull.number}`}
            className="inline-flex items-center gap-1 px-2 py-1 text-2xs text-muted-foreground hover:text-foreground"
            href={pull.htmlUrl}
            rel="noreferrer"
            target="_blank"
          >
            <ExternalLink className="h-3 w-3" />
            GitHub
          </a>
        </ProjectFeedRowCluster>
      }
    />
  );
}

export function GithubPullRequestsSection({
  cloneUrl,
}: {
  cloneUrl: string | null | undefined;
}) {
  const githubPullsQuery = useGithubOpenPullsQuery(cloneUrl);
  if (!parseGithubHttpsRepo(cloneUrl)) return null;

  const githubPulls = githubPullsQuery.data ?? [];
  return (
    <section
      className="border-t border-border/60"
      data-testid="github-pull-requests"
    >
      <div className="flex min-h-10 items-center gap-2 bg-muted/20 px-4">
        <GitHubMark className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-sm font-medium text-foreground">On GitHub</span>
        <span className="text-2xs text-muted-foreground">
          Opens on github.com — merge stays there
        </span>
      </div>
      {githubPullsQuery.isLoading ? (
        <p className="p-4 text-sm text-muted-foreground">
          Loading GitHub pull requests…
        </p>
      ) : githubPullsQuery.error ? (
        <p className="p-4 text-sm text-muted-foreground">
          Could not load open GitHub pull requests.
        </p>
      ) : githubPulls.length === 0 ? (
        <p className="p-4 text-sm text-muted-foreground">
          No open pull requests on GitHub.
        </p>
      ) : (
        <div className="divide-y divide-border/50">
          {githubPulls.map((pull) => (
            <GithubPullRequestRow key={pull.number} pull={pull} />
          ))}
        </div>
      )}
    </section>
  );
}

export function hasGithubCloneUrl(cloneUrl: string | null | undefined) {
  return Boolean(parseGithubHttpsRepo(cloneUrl));
}
