import { Trash2 } from "lucide-react";
import * as React from "react";

import type { Project, Repository } from "@/features/projects/hooks";
import { unlistConfirmCopy } from "@/features/projects/unlistProjectRepository";
import { Button } from "@/shared/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/shared/ui/alert-dialog";
import { DropdownMenuItem } from "@/shared/ui/dropdown-menu";

export function UnlistProjectRepositoryMenuItem({
  disabled,
  onUnlist,
  repository,
}: {
  disabled?: boolean;
  onUnlist: () => Promise<void> | void;
  project: Project;
  repository: Repository;
}) {
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const copy = unlistConfirmCopy(repository.name);
  return (
    <AlertDialog onOpenChange={setConfirmOpen} open={confirmOpen}>
      <DropdownMenuItem
        className="text-destructive focus:text-destructive"
        data-testid={`repository-unlist-${repository.dtag}`}
        disabled={disabled}
        onSelect={(event) => {
          event.preventDefault();
          event.stopPropagation();
          if (!disabled) setConfirmOpen(true);
        }}
      >
        <Trash2 className="h-4 w-4" />
        Unlist from Buzz
      </DropdownMenuItem>
      <AlertDialogContent
        data-testid={`repository-unlist-confirm-${repository.dtag}`}
      >
        <AlertDialogHeader>
          <AlertDialogTitle>{copy.title}</AlertDialogTitle>
          <AlertDialogDescription>{copy.description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel asChild>
            <Button disabled={disabled} type="button" variant="outline">
              Cancel
            </Button>
          </AlertDialogCancel>
          <AlertDialogAction asChild>
            <Button
              data-testid={`repository-unlist-confirm-button-${repository.dtag}`}
              disabled={disabled}
              onClick={(event) => {
                event.preventDefault();
                void Promise.resolve(onUnlist()).finally(() =>
                  setConfirmOpen(false),
                );
              }}
              type="button"
              variant="destructive"
            >
              {disabled ? "Unlisting…" : "Unlist from Buzz"}
            </Button>
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function UnlistProjectRepositoryIconButton({
  disabled,
  onUnlist,
  repository,
}: {
  disabled?: boolean;
  onUnlist: () => Promise<void> | void;
  repository: Repository;
}) {
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const copy = unlistConfirmCopy(repository.name);
  return (
    <AlertDialog onOpenChange={setConfirmOpen} open={confirmOpen}>
      <AlertDialogTrigger asChild>
        <Button
          aria-label={`Unlist ${repository.name} from Buzz`}
          className="h-6 w-6 shrink-0 text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-destructive"
          data-testid={`repository-unlist-icon-${repository.dtag}`}
          disabled={disabled}
          onClick={(event) => event.stopPropagation()}
          size="icon"
          title="Unlist from Buzz"
          type="button"
          variant="ghost"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent
        data-testid={`repository-unlist-confirm-${repository.dtag}`}
      >
        <AlertDialogHeader>
          <AlertDialogTitle>{copy.title}</AlertDialogTitle>
          <AlertDialogDescription>{copy.description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel asChild>
            <Button disabled={disabled} type="button" variant="outline">
              Cancel
            </Button>
          </AlertDialogCancel>
          <AlertDialogAction asChild>
            <Button
              data-testid={`repository-unlist-confirm-button-${repository.dtag}`}
              disabled={disabled}
              onClick={(event) => {
                event.preventDefault();
                void Promise.resolve(onUnlist()).finally(() =>
                  setConfirmOpen(false),
                );
              }}
              type="button"
              variant="destructive"
            >
              {disabled ? "Unlisting…" : "Unlist from Buzz"}
            </Button>
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
