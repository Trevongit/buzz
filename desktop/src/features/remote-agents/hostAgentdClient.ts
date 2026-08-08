import type { HostAgentStatus, RemoteAgentPreset } from "./types";

export class HostAgentdError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "HostAgentdError";
    this.status = status;
  }
}

function authHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
  };
}

async function parseJson(res: Response): Promise<unknown> {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { raw: text };
  }
}

export async function hostAgentdHealth(
  baseUrl: string,
  token: string,
): Promise<{ ok: boolean; service?: string }> {
  const res = await fetch(`${baseUrl.replace(/\/$/, "")}/v1/health`, {
    headers: authHeaders(token),
  });
  const body = (await parseJson(res)) as { ok?: boolean; service?: string };
  if (!res.ok) {
    throw new HostAgentdError(
      (body as { error?: string }).error || `health ${res.status}`,
      res.status,
    );
  }
  return { ok: Boolean(body.ok), service: body.service };
}

export async function hostAgentdStatus(
  baseUrl: string,
  token: string,
): Promise<HostAgentStatus> {
  const res = await fetch(`${baseUrl.replace(/\/$/, "")}/v1/status`, {
    headers: authHeaders(token),
  });
  const body = (await parseJson(res)) as HostAgentStatus;
  if (!res.ok) {
    throw new HostAgentdError(body.error || `status ${res.status}`, res.status);
  }
  return body;
}

export async function hostAgentdArm(
  baseUrl: string,
  token: string,
  seatId: string,
  preset: RemoteAgentPreset,
  room?: string,
): Promise<{ ok: boolean; stdout?: string; stderr?: string }> {
  const res = await fetch(
    `${baseUrl.replace(/\/$/, "")}/v1/agents/${encodeURIComponent(seatId)}/arm`,
    {
      method: "POST",
      headers: {
        ...authHeaders(token),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ preset, room: room || undefined }),
    },
  );
  const body = (await parseJson(res)) as {
    ok?: boolean;
    error?: string;
    stdout?: string;
    stderr?: string;
  };
  if (!res.ok || body.ok === false) {
    throw new HostAgentdError(
      body.error || body.stderr || `arm ${res.status}`,
      res.status,
    );
  }
  return { ok: true, stdout: body.stdout, stderr: body.stderr };
}

export async function hostAgentdDisarm(
  baseUrl: string,
  token: string,
  seatId: string,
  preset: RemoteAgentPreset,
): Promise<{ ok: boolean; stdout?: string; stderr?: string }> {
  const res = await fetch(
    `${baseUrl.replace(/\/$/, "")}/v1/agents/${encodeURIComponent(seatId)}/disarm`,
    {
      method: "POST",
      headers: {
        ...authHeaders(token),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ preset }),
    },
  );
  const body = (await parseJson(res)) as {
    ok?: boolean;
    error?: string;
    stdout?: string;
    stderr?: string;
  };
  if (!res.ok || body.ok === false) {
    throw new HostAgentdError(
      body.error || body.stderr || `disarm ${res.status}`,
      res.status,
    );
  }
  return { ok: true, stdout: body.stdout, stderr: body.stderr };
}
