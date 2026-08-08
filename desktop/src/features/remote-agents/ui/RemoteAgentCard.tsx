import { Loader2, Play, Square } from "lucide-react";

import type { RemoteAgentCardModel, RemoteAgentPreset } from "../types";
import { cn } from "@/shared/lib/cn";
import { Button } from "@/shared/ui/button";

type RemoteAgentCardProps = {
  card: RemoteAgentCardModel;
  isPending: boolean;
  defaultPreset: RemoteAgentPreset;
  onArm: () => void;
  onDisarm: () => void;
};

function healthDotClass(health: RemoteAgentCardModel["health"]): string {
  switch (health) {
    case "online":
      return "bg-emerald-500";
    case "stale":
      return "bg-amber-500";
    case "stopped":
      return "bg-rose-500";
    default:
      return "bg-muted-foreground/50";
  }
}

export function RemoteAgentCard({
  card,
  isPending,
  defaultPreset,
  onArm,
  onDisarm,
}: RemoteAgentCardProps) {
  return (
    <div
      className="flex min-h-[140px] flex-col justify-between rounded-xl border border-border/60 bg-card p-3 shadow-sm"
      data-testid={`remote-agent-card-${card.seatId}`}
    >
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className={cn(
              "h-2.5 w-2.5 shrink-0 rounded-full",
              healthDotClass(card.health),
            )}
          />
          <p className="truncate text-sm font-semibold text-foreground">
            {card.seatId}
          </p>
        </div>
        <p className="truncate text-2xs text-muted-foreground">
          {card.hostId} · {card.hostRole}
        </p>
        <p className="truncate text-2xs text-muted-foreground">
          {card.healthLabel}
          {card.model ? ` · ${card.model}` : ""}
        </p>
        {card.runtimes.length > 0 ? (
          <p className="truncate text-2xs text-muted-foreground/80">
            {card.runtimes.join(" · ")}
          </p>
        ) : null}
      </div>
      <div className="mt-3 flex items-center gap-2">
        <Button
          className="h-8 flex-1 gap-1 text-xs"
          disabled={isPending || card.seatId.startsWith("(")}
          size="sm"
          type="button"
          variant="secondary"
          onClick={onArm}
        >
          {isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Play className="h-3.5 w-3.5" />
          )}
          Arm
        </Button>
        <Button
          className="h-8 flex-1 gap-1 text-xs"
          disabled={isPending || card.seatId.startsWith("(")}
          size="sm"
          type="button"
          variant="outline"
          onClick={onDisarm}
        >
          <Square className="h-3.5 w-3.5" />
          Stop
        </Button>
      </div>
      <p className="mt-1 truncate text-3xs text-muted-foreground/70">
        preset {defaultPreset}
      </p>
    </div>
  );
}
