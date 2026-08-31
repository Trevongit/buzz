import type * as React from "react";
import { toast } from "sonner";

import {
  pauseListenPlayback,
  resumeListenPlayback,
  speakListenText,
  stopListenPlayback,
} from "@/features/messages/lib/listenPlayback";
import { readListenSummaryAgentPreference } from "@/features/messages/lib/listenSummaryAgentPreference";
import {
  isFollowAlongMessage,
  spokenProseFromReaderReply,
} from "@/features/messages/lib/listenSpeech";
import { useListenPlayback } from "@/features/messages/lib/useListenPlayback";
import type { TimelineMessage } from "@/features/messages/types";
import { useFeatureEnabled } from "@/shared/features";
import { Button } from "@/shared/ui/button";

const CONTROL_BUTTON_CLASS = "h-8 w-fit rounded-full px-3";

export function MessageFollowAlong({
  message,
  children,
}: {
  message: TimelineMessage;
  children: React.ReactNode;
}) {
  const listenEnabled = useFeatureEnabled("pocketListen");
  const playback = useListenPlayback();
  if (
    !listenEnabled ||
    !isFollowAlongMessage(message, readListenSummaryAgentPreference()?.name)
  ) {
    return children;
  }

  const playFollowAlong = () => {
    toast.message("Following along…");
    void speakListenText(spokenProseFromReaderReply(message.body)).catch(
      (error) => {
        toast.error("Could not listen", {
          description:
            error instanceof Error ? error.message : "Check Voice settings.",
        });
      },
    );
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          className={CONTROL_BUTTON_CLASS}
          data-testid={`follow-along-${message.id}`}
          onClick={playFollowAlong}
          size="sm"
          type="button"
          variant="secondary"
        >
          Follow along
        </Button>
        {playback === "playing" || playback === "paused" ? (
          <>
            {playback === "playing" ? (
              <Button
                className={CONTROL_BUTTON_CLASS}
                data-testid={`listen-pause-${message.id}`}
                onClick={() => {
                  void pauseListenPlayback();
                }}
                size="sm"
                type="button"
                variant="ghost"
              >
                Pause
              </Button>
            ) : (
              <Button
                className={CONTROL_BUTTON_CLASS}
                data-testid={`listen-resume-${message.id}`}
                onClick={() => {
                  void resumeListenPlayback().catch((error) => {
                    toast.error("Could not listen", {
                      description:
                        error instanceof Error
                          ? error.message
                          : "Check Voice settings.",
                    });
                  });
                }}
                size="sm"
                type="button"
                variant="ghost"
              >
                Resume
              </Button>
            )}
            <Button
              className={CONTROL_BUTTON_CLASS}
              data-testid={`listen-stop-${message.id}`}
              onClick={() => {
                void stopListenPlayback();
              }}
              size="sm"
              type="button"
              variant="ghost"
            >
              Stop
            </Button>
          </>
        ) : null}
      </div>
      {children}
    </div>
  );
}
