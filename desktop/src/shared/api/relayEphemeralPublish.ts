import { signRelayEvent } from "@/shared/api/tauri";
import type { PresenceStatus, RelayEvent } from "@/shared/api/types";
import {
  KIND_TYPING_INDICATOR,
  KIND_USER_STATUS,
} from "@/shared/constants/kinds";
import { buildThreadReferenceTags } from "@/features/messages/lib/threading";

type UserStatusInput = { text: string; emoji: string; expiresAt?: number };

export function buildPresenceEvent(
  status: PresenceStatus,
): Promise<RelayEvent> {
  return signRelayEvent({
    kind: 20001,
    content: status,
    tags: [],
  });
}

/** Ephemeral typing. Callers skip this when the socket is down. */
export function buildTypingIndicatorEvent(
  channelId: string,
  parentEventId?: string | null,
  rootEventId?: string | null,
): Promise<RelayEvent> {
  return signRelayEvent({
    kind: KIND_TYPING_INDICATOR,
    content: "",
    tags: buildThreadReferenceTags(
      channelId,
      parentEventId ?? null,
      rootEventId ?? null,
    ),
  });
}

export function buildUserStatusEvent(
  status: UserStatusInput,
): Promise<RelayEvent> {
  const tags: string[][] = [["d", "general"]];
  if (status.emoji) tags.push(["emoji", status.emoji]);
  if (status.expiresAt) tags.push(["expiration", String(status.expiresAt)]);
  return signRelayEvent({
    kind: KIND_USER_STATUS,
    content: status.text,
    tags,
  });
}
