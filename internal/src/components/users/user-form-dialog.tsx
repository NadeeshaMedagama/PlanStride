import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getUserListQueryKey,
  useUserUpdate,
} from "@/api/endpoints/users/users";
import type { InternalUserResponse } from "@/api/model";
import { applyApiErrorToForm } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

// Support edits only: fixing a name or an email address. Accounts are created
// by sign-up, staff access only with `manage.py create-user --admin`.
const schema = z.object({
  first_name: z.string().trim().min(1, "First name is required").max(100),
  last_name: z.string().trim().min(1, "Last name is required").max(100),
  email: z.string().min(1, "Email is required").email("Invalid email address"),
});

type UserFormData = z.infer<typeof schema>;

interface UserFormDialogProps {
  user: InternalUserResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UserFormDialog({
  user,
  open,
  onOpenChange,
}: UserFormDialogProps) {
  const queryClient = useQueryClient();
  const form = useForm<UserFormData>({
    resolver: zodResolver(schema),
    defaultValues: { first_name: "", last_name: "", email: "" },
    mode: "onTouched",
  });

  // Seed the form from the selected user each time the dialog opens, so stale
  // input from a previous edit never leaks in.
  useEffect(() => {
    if (open && user) {
      form.reset({
        first_name: user.first_name,
        last_name: user.last_name,
        email: user.email,
      });
    }
  }, [open, user, form]);

  const mutation = useUserUpdate({
    mutation: {
      onSuccess: async () => {
        await queryClient.invalidateQueries({
          queryKey: getUserListQueryKey(),
        });
        toast.success("User updated");
        onOpenChange(false);
      },
      onError: (error) => {
        const formError = applyApiErrorToForm(error, form.setError, {
          fields: ["first_name", "last_name", "email"],
          fallback: "Failed to update user",
        });
        if (formError) {
          toast.error(formError);
        }
      },
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit user</DialogTitle>
          <DialogDescription>
            Correct this person&apos;s name or email address.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(
              (data) => user && mutation.mutate({ userId: user.id, data })
            )}
            className="space-y-4"
            noValidate
          >
            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={form.control}
                name="first_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>First name</FormLabel>
                    <FormControl>
                      <Input autoComplete="off" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="last_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Last name</FormLabel>
                    <FormControl>
                      <Input autoComplete="off" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input type="email" autoComplete="off" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => onOpenChange(false)}
                disabled={mutation.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "Saving…" : "Save changes"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
