import * as React from "react";

import {
  getListenPlaybackStatus,
  subscribeListenPlayback,
  type ListenPlaybackStatus,
} from "@/features/messages/lib/listenPlayback";

export function useListenPlayback(): ListenPlaybackStatus {
  return React.useSyncExternalStore(
    subscribeListenPlayback,
    getListenPlaybackStatus,
    getListenPlaybackStatus,
  );
}
