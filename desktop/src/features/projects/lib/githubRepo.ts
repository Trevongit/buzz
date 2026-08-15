/** Parse a public https://github.com/owner/repo(.git) clone URL. */
export function parseGithubHttpsRepo(
  cloneUrl: string | null | undefined,
): { owner: string; repo: string } | null {
  if (!cloneUrl) return null;
  let parsed: URL;
  try {
    parsed = new URL(cloneUrl.trim());
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:") return null;
  if (parsed.hostname.toLowerCase() !== "github.com") return null;
  if (
    parsed.port ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash
  ) {
    return null;
  }
  const parts = parsed.pathname.split("/").filter(Boolean);
  if (parts.length !== 2) return null;
  const owner = parts[0];
  const repo = parts[1].replace(/\.git$/i, "");
  if (!owner || !repo) return null;
  return { owner, repo };
}

export function githubPullsApiUrl(
  cloneUrl: string | null | undefined,
): string | null {
  const parsed = parseGithubHttpsRepo(cloneUrl);
  if (!parsed) return null;
  return `https://api.github.com/repos/${parsed.owner}/${parsed.repo}/pulls?state=open&per_page=30`;
}

export function githubRepoHtmlUrl(
  cloneUrl: string | null | undefined,
): string | null {
  const parsed = parseGithubHttpsRepo(cloneUrl);
  if (!parsed) return null;
  return `https://github.com/${parsed.owner}/${parsed.repo}`;
}
