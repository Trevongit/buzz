import { Volume2 } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { speakListenText } from "@/features/messages/lib/listenPlayback";
import {
  resolveReaderAgent,
  summarizeWithReader,
} from "@/features/messages/lib/listenReader";
import { listenPlainText } from "@/features/messages/lib/listenSpeech";
import type { TimelineMessage } from "@/features/messages/types";
import { Button } from "@/shared/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip";

const ACTION_BUTTON_CLASS = "h-8 w-8 rounded-full p-0";
const ACTION_ICON_CLASS = "!h-4 !w-4";

function formatElapsed(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function MessageListenButton({
  channelId,
  message,
  onOpenChange,
}: {
  channelId?: string | null;
  message: TimelineMessage;
  onOpenChange: (open: boolean) => void;
}) {
  const [busy, setBusy] = React.useState(false);
  const plain = listenPlainText(message.body);
  if (!plain) return null;

  const run = async (mode: "play" | "summary") => {
    if (busy) return;
    setBusy(true);
    try {
      if (mode === "play") {
        toast.message("Listening…");
        await speakListenText(plain);
        return;
      }
      if (!channelId || message.pending) {
        throw new Error("Listen (summary) needs a delivered channel message.");
      }
      const agent = await resolveReaderAgent();
      const waitToast = toast.loading(
        `Asking ${agent.name}… Pocket starts when they post. 0:00`,
      );
      const started = Date.now();
      const tick = window.setInterval(() => {
        const elapsed = Math.floor((Date.now() - started) / 1000);
        toast.loading(
          `Asking ${agent.name}… still searching ${formatElapsed(elapsed)}. Pocket starts when they post.`,
          { id: waitToast },
        );
      }, 1000);
      try {
        const { summary } = await summarizeWithReader({
          agent,
          channelId,
          messageId: message.id,
          text: plain,
        });
        toast.success("Listening to summary…", { id: waitToast });
        await speakListenText(summary);
      } catch (error) {
        toast.dismiss(waitToast);
        throw error;
      } finally {
        window.clearInterval(tick);
      }
    } catch (error) {
      toast.error("Could not listen", {
        description:
          error instanceof Error
            ? error.message
            : "Check that a Listen (summary) agent is running.",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <DropdownMenu onOpenChange={onOpenChange}>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <Button
              aria-label="Listen to message"
              className={ACTION_BUTTON_CLASS}
              data-testid={`listen-message-${message.id}`}
              disabled={busy}
              size="sm"
              type="button"
              variant="ghost"
            >
              <Volume2 className={ACTION_ICON_CLASS} />
            </Button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent>Listen</TooltipContent>
      </Tooltip>
      <DropdownMenuContent align="end" side="top" sideOffset={8}>
        <DropdownMenuItem
          disabled={busy}
          onSelect={() => {
            void run("play");
          }}
        >
          Listen
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={busy}
          onSelect={() => {
            void run("summary");
          }}
        >
          Listen (summary)
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
