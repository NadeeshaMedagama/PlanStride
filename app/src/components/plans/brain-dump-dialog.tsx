import { useState } from "react";
import { Wand2 } from "lucide-react";
import { useAiPlanDraft } from "@/api/endpoints/ai/ai";
import type { PlanDraftResponse } from "@/api/model";
import { AiErrorAlert } from "@/components/plans/ai-review";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

const PLACEHOLDER =
  "need to finish the billing page, probably also fix that webhook bug, " +
  "should announce it in the changelog…";

// Messy notes in, a structured plan out. The draft goes into the editor for
// the member to change; nothing is saved by this dialog.
export function BrainDumpDialog({
  open,
  onOpenChange,
  orgId,
  weekStart,
  replacing,
  onDraft,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgId: string;
  weekStart: string;
  replacing: boolean;
  onDraft: (draft: PlanDraftResponse) => void;
}) {
  const [notes, setNotes] = useState("");
  const draft = useAiPlanDraft({
    mutation: {
      onSuccess: (result) => {
        onDraft(result);
        onOpenChange(false);
      },
    },
  });
  const tooShort = notes.trim().length < 10;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        // Don't drop the request's result by closing mid-flight.
        if (!draft.isPending) {
          onOpenChange(next);
        }
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Draft my plan from notes</DialogTitle>
          <DialogDescription>
            Paste whatever&apos;s on your mind for the week. PlanStride turns it
            into a main task, sub-goals and go-to-market goals for you to edit.
            Nothing is saved until you click Save.
          </DialogDescription>
        </DialogHeader>
        <Textarea
          autoFocus
          rows={7}
          maxLength={4000}
          placeholder={PLACEHOLDER}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          disabled={draft.isPending}
          aria-label="Your notes for the week"
        />
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {replacing ? "The draft replaces what's in the editor now." : " "}
          </span>
          <span className="tabular-nums">{notes.length}/4000</span>
        </div>
        {draft.isError && (
          <AiErrorAlert error={draft.error} onDismiss={() => draft.reset()} />
        )}
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={draft.isPending}
          >
            Cancel
          </Button>
          <Button
            disabled={tooShort || draft.isPending}
            onClick={() =>
              draft.mutate({
                organizationId: orgId,
                data: { week_start: weekStart, notes: notes.trim() },
              })
            }
          >
            {draft.isPending ? <Spinner /> : <Wand2 className="size-4" />}
            {draft.isPending ? "Drafting your plan…" : "Draft my plan"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
