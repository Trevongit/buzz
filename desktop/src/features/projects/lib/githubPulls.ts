import { githubPullsApiUrl, parseGithubHttpsRepo } from "./githubRepo";

export type GithubPullSummary = {
  number: number;
  title: string;
  htmlUrl: string;
  userLogin: string;
  createdAt: number;
  draft: boolean;
  headRef: string;
  baseRef: string;
};

type GithubPullJson = {
  number?: number;
  title?: string;
  html_url?: string;
  draft?: boolean;
  created_at?: string;
  user?: { login?: string };
  head?: { ref?: string };
  base?: { ref?: string };
};

export function mapGithubPulls(payload: unknown): GithubPullSummary[] {
  if (!Array.isArray(payload)) return [];
  return payload.flatMap((item) => {
    const row = item as GithubPullJson;
    if (
      typeof row.number !== "number" ||
      typeof row.title !== "string" ||
      typeof row.html_url !== "string"
    ) {
      return [];
    }
    const createdAt = Date.parse(row.created_at ?? "");
    return [
      {
        number: row.number,
        title: row.title,
        htmlUrl: row.html_url,
        userLogin: row.user?.login ?? "unknown",
        createdAt: Number.isFinite(createdAt)
          ? Math.floor(createdAt / 1000)
          : 0,
        draft: Boolean(row.draft),
        headRef: row.head?.ref ?? "",
        baseRef: row.base?.ref ?? "",
      },
    ];
  });
}

function e2eGithubPulls(
  cloneUrl: string | null | undefined,
): GithubPullSummary[] | null {
  if (typeof window === "undefined") return null;
  const e2eWindow = window as Window & {
    __BUZZ_E2E__?: unknown;
    __BUZZ_E2E_GITHUB_PULLS__?: unknown;
  };
  if (!e2eWindow.__BUZZ_E2E__) return null;
  if (e2eWindow.__BUZZ_E2E_GITHUB_PULLS__ !== undefined) {
    return mapGithubPulls(e2eWindow.__BUZZ_E2E_GITHUB_PULLS__);
  }
  const parsed = parseGithubHttpsRepo(cloneUrl);
  if (parsed?.owner === "block" && parsed.repo === "relay-tools") {
    return [
      {
        number: 12,
        title: "Document operator backup restore",
        htmlUrl: "https://github.com/block/relay-tools/pull/12",
        userLogin: "alice",
        createdAt: 1_700_000_000,
        draft: false,
        headRef: "docs/backup",
        baseRef: "main",
      },
    ];
  }
  return [];
}

/** Public GitHub pull list. No token — 60 req/hr unauthenticated. */
export async function fetchGithubOpenPulls(
  cloneUrl: string | null | undefined,
): Promise<GithubPullSummary[]> {
  const e2ePulls = e2eGithubPulls(cloneUrl);
  if (e2ePulls) return e2ePulls;

  const url = githubPullsApiUrl(cloneUrl);
  if (!url) return [];

  const response = await fetch(url, {
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "Buzz-Desktop",
    },
  });
  if (!response.ok) {
    throw new Error(`GitHub pulls ${response.status}`);
  }
  return mapGithubPulls(await response.json());
}
