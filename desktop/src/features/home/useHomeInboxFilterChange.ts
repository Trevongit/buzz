import * as React from "react";

import type { InboxFilter, InboxItem } from "@/features/home/lib/inbox";
import { resolveInboxFilterSelection } from "@/features/home/lib/inboxSelection";
import { filterVisibleInboxItems } from "@/features/home/lib/inboxViewHelpers";

type UseHomeInboxFilterChangeOptions = {
  applyInboxSearchPatch: (patch: { item: string | null }) => void;
  effectiveDoneSet: ReadonlySet<string>;
  inboxItems: InboxItem[];
  isNarrowHomeViewport: boolean;
  ownedAgentPubkeys: ReadonlySet<string>;
  selectedConversationId: string | null;
  setAutoSelectedEventId: React.Dispatch<React.SetStateAction<string | null>>;
  setFilter: React.Dispatch<React.SetStateAction<InboxFilter>>;
  setSelectedDraftKey: (key: string | null) => void;
  setSelectedReminderId: (id: string | null) => void;
  setUnreadBoundary: React.Dispatch<
    React.SetStateAction<{ conversationId: string; eventId: string } | null>
  >;
  unreadOnly: boolean;
  urlSelectedItemId: string | null;
};

export function useHomeInboxFilterChange({
  applyInboxSearchPatch,
  effectiveDoneSet,
  inboxItems,
  isNarrowHomeViewport,
  ownedAgentPubkeys,
  selectedConversationId,
  setAutoSelectedEventId,
  setFilter,
  setSelectedDraftKey,
  setSelectedReminderId,
  setUnreadBoundary,
  unreadOnly,
  urlSelectedItemId,
}: UseHomeInboxFilterChangeOptions) {
  return React.useCallback(
    (nextFilter: InboxFilter) => {
      const nextItems = filterVisibleInboxItems(inboxItems, {
        doneSet: effectiveDoneSet,
        filter: nextFilter,
        ownedAgentPubkeys,
        selectedConversationId,
        unreadOnly,
        urlSelectedItemId,
      });
      const selection = resolveInboxFilterSelection({
        isNarrow: isNarrowHomeViewport,
        items: nextItems,
        selectedConversationId,
      });

      setUnreadBoundary(null);
      setSelectedDraftKey(null);
      setSelectedReminderId(null);
      setFilter(nextFilter);

      if (
        nextFilter === "reminders" ||
        nextFilter === "drafts" ||
        selection.preserveSelection
      ) {
        if (nextFilter === "reminders" || nextFilter === "drafts") {
          setAutoSelectedEventId(null);
          applyInboxSearchPatch({ item: null });
        }
        return;
      }

      applyInboxSearchPatch({ item: null });
      setAutoSelectedEventId(selection.autoSelectedEventId);
    },
    [
      applyInboxSearchPatch,
      effectiveDoneSet,
      inboxItems,
      isNarrowHomeViewport,
      ownedAgentPubkeys,
      selectedConversationId,
      setAutoSelectedEventId,
      setFilter,
      setSelectedDraftKey,
      setSelectedReminderId,
      setUnreadBoundary,
      unreadOnly,
      urlSelectedItemId,
    ],
  );
}
