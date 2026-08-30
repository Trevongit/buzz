import {
  finishSpokenSummary,
  isReaderAgentName,
  listenReaderAsk,
  READER_AGENT_NAME,
  spokenProseFromReaderReply,
} from "@/features/messages/lib/listenSpeech";
import { relayClient } from "@/shared/api/relayClient";
import { startManagedAgent } from "@/shared/api/tauriManagedAgents";
import {
  getThreadReplies,
  listManagedAgents,
  sendChannelMessage,
} from "@/shared/api/tauri";
import type { ManagedAgent, RelayEvent } from "@/shared/api/types";

const READER_REPLY_TIMEOUT_MS = 240_000;
const READER_REPLY_POLL_MS = 2_000;

export async function resolveReaderAgent(): Promise<ManagedAgent> {
  const agents = await listManagedAgents();
  const reader = agents.find((agent) => isReaderAgentName(agent.name));
  if (!reader) {
    throw new Error(
      `${READER_AGENT_NAME} is not added yet. Add that agent in Agents, then try Listen (summary) again.`,
    );
  }
  if (reader.status === "stopped" || reader.status === "not_deployed") {
    await startManagedAgent(reader.pubkey);
  }
  return reader;
}

export async function summarizeWithReader(input: {
  channelId: string;
  messageId: string;
  text: string;
}): Promise<string> {
  const reader = await resolveReaderAgent();
  const waiting = waitForReaderReply({
    channelId: input.channelId,
    readerPubkey: reader.pubkey,
    since: Math.floor(Date.now() / 1000) - 2,
    threadRootId: input.messageId,
  });
  await waiting.ready;
  const sent = await sendChannelMessage(
    input.channelId,
    listenReaderAsk(input.text),
    input.messageId,
    undefined,
    [reader.pubkey],
  );
  waiting.setAskEventId(sent.eventId);
  const reply = await waiting.reply;
  const spoken = spokenProseFromReaderReply(reply);
  if (!spoken) {
    throw new Error(`${READER_AGENT_NAME} returned nothing to speak.`);
  }
  return finishSpokenSummary(spoken);
}

function isReplyToAsk(event: RelayEvent, askEventId: string | null): boolean {
  if (!askEventId) return false;
  return event.tags.some(
    (tag) =>
      tag[0] === "e" && tag[1]?.toLowerCase() === askEventId.toLowerCase(),
  );
}

async function pollThreadForReply(
  channelId: string,
  rootEventId: string,
  consider: (event: RelayEvent) => void,
) {
  try {
    const page = await getThreadReplies(rootEventId, channelId, { limit: 80 });
    for (const event of page.events) consider(event);
  } catch {
    // Live subscribe remains the primary path.
  }
}

function waitForReaderReply(input: {
  channelId: string;
  readerPubkey: string;
  since: number;
  threadRootId: string;
}): {
  ready: Promise<void>;
  reply: Promise<string>;
  setAskEventId: (eventId: string) => void;
} {
  let unsubscribe: (() => Promise<void>) | null = null;
  let settled = false;
  let askEventId: string | null = null;
  const pending: RelayEvent[] = [];
  let resolveReady: () => void = () => {};
  let consider: (event: RelayEvent) => void = () => {};
  const ready = new Promise<void>((resolve) => {
    resolveReady = resolve;
  });

  const reply = new Promise<string>((resolve, reject) => {
    let pollId = 0;
    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeoutId);
      window.clearInterval(pollId);
      void unsubscribe?.();
      fn();
    };

    const timeoutId = window.setTimeout(() => {
      finish(() =>
        reject(
          new Error(
            `${READER_AGENT_NAME} is still writing. Wait for their post in this thread, then click Follow along.`,
          ),
        ),
      );
    }, READER_REPLY_TIMEOUT_MS);

    pollId = window.setInterval(() => {
      const roots = [input.threadRootId, askEventId].filter(
        (id): id is string => Boolean(id),
      );
      for (const root of new Set(roots)) {
        void pollThreadForReply(input.channelId, root, consider);
      }
    }, READER_REPLY_POLL_MS);

    consider = (event: RelayEvent) => {
      if (settled) return;
      if (event.created_at < input.since) return;
      if (!askEventId) {
        pending.push(event);
        return;
      }
      if (event.id.toLowerCase() === askEventId.toLowerCase()) return;
      const fromReader =
        event.pubkey.toLowerCase() === input.readerPubkey.toLowerCase();
      if (!fromReader && !isReplyToAsk(event, askEventId)) return;
      const body = event.content?.trim();
      if (!body) return;
      finish(() => resolve(body));
    };

    const onEvent = (event: RelayEvent) => {
      consider(event);
    };

    void relayClient
      .subscribeToChannelLive(input.channelId, onEvent)
      .then((stop) => {
        unsubscribe = stop;
        resolveReady();
        if (settled) void stop();
      })
      .catch((error) => {
        resolveReady();
        finish(() =>
          reject(
            error instanceof Error
              ? error
              : new Error("Could not wait for Reader-laptop."),
          ),
        );
      });
  });

  return {
    ready,
    reply,
    setAskEventId: (eventId: string) => {
      askEventId = eventId;
      for (const event of pending) consider(event);
      pending.length = 0;
    },
  };
}
