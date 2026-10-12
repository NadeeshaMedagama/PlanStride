import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Users } from "lucide-react";
import { useSignup } from "@/api/endpoints/auth/auth";
import { useInvitationPreview } from "@/api/endpoints/invitations/invitations";
import { applyApiErrorToForm } from "@/lib/api-error";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

const baseSchema = z.object({
  first_name: z.string().trim().min(1, "First name is required").max(100),
  last_name: z.string().trim().min(1, "Last name is required").max(100),
  email: z.string().min(1, "Email is required").email("Invalid email address"),
  password: z
    .string()
    .min(8, "Use at least 8 characters")
    .max(128, "That's too long"),
  organization_name: z.string(),
});

const createSchema = baseSchema.extend({
  organization_name: z
    .string()
    .trim()
    .min(2, "Name your organization")
    .max(120),
});

type SignupFormData = z.infer<typeof baseSchema>;

const FIELDS = [
  "first_name",
  "last_name",
  "email",
  "password",
  "organization_name",
] as const;

export const Route = createFileRoute("/signup")({
  validateSearch: (search: Record<string, unknown>): { invite?: string } => ({
    invite: typeof search["invite"] === "string" ? search["invite"] : undefined,
  }),
  head: () => ({ meta: [{ title: "Create your account · PlanStride" }] }),
  component: Signup,
});

function Signup() {
  const { invite } = Route.useSearch();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const preview = useInvitationPreview(invite ?? "", {
    query: { enabled: Boolean(invite), retry: false },
  });
  const joining = Boolean(invite);

  const form = useForm<SignupFormData>({
    resolver: zodResolver(joining ? baseSchema : createSchema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email: "",
      password: "",
      organization_name: "",
    },
    mode: "onTouched",
  });

  const signup = useSignup({
    mutation: {
      onSuccess: () => {
        queryClient.clear();
        navigate({ to: "/" });
      },
      onError: (error) => {
        setFormError(
          applyApiErrorToForm(error, form.setError, {
            fields: FIELDS,
            fallback: "We couldn't create your account. Please try again.",
          })
        );
      },
    },
  });

  const onSubmit = (data: SignupFormData) => {
    setFormError(null);
    signup.mutate({
      data: {
        first_name: data.first_name,
        last_name: data.last_name,
        email: data.email,
        password: data.password,
        organization_name: joining ? null : data.organization_name,
        invite_token: joining ? (invite ?? null) : null,
      },
    });
  };

  return (
    <div className="flex min-h-dvh items-center justify-center bg-muted/30 p-6">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-6 text-center">
          <Logo className="h-9" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {joining ? "Join your team" : "Start planning with your team"}
            </h1>
            <p className="mt-1.5 text-sm text-muted-foreground">
              {joining
                ? "Create your account to accept the invite."
                : "Create your account and your organization. Invite your team next."}
            </p>
          </div>
        </div>

        {joining && (
          <div className="mb-4 rounded-xl border bg-background p-4">
            {preview.isLoading && <Skeleton className="h-10 w-full" />}
            {preview.isError && (
              <p className="text-sm text-destructive">
                This invite link is invalid or has expired. Ask whoever sent it
                for a new one, or{" "}
                <Link to="/signup" className="underline">
                  start your own organization
                </Link>
                .
              </p>
            )}
            {preview.data && (
              <div className="flex items-center gap-3">
                <span className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Users className="size-5" />
                </span>
                <div className="text-sm">
                  <p className="font-medium">
                    You&apos;re joining {preview.data.organization_name}
                  </p>
                  <p className="text-muted-foreground">
                    as {preview.data.role === "admin" ? "an admin" : "a member"}
                    {preview.data.invited_by
                      ? `, invited by ${preview.data.invited_by}`
                      : ""}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        <div className="rounded-xl border bg-background p-6 shadow-sm">
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
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
                        <Input
                          autoComplete="given-name"
                          className="h-10"
                          {...field}
                        />
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
                        <Input
                          autoComplete="family-name"
                          className="h-10"
                          {...field}
                        />
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
                    <FormLabel>Work email</FormLabel>
                    <FormControl>
                      <Input
                        type="email"
                        autoComplete="email"
                        placeholder="you@company.com"
                        className="h-10"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        autoComplete="new-password"
                        placeholder="At least 8 characters"
                        className="h-10"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {!joining && (
                <FormField
                  control={form.control}
                  name="organization_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Organization</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="e.g. Northwind Labs"
                          autoComplete="organization"
                          className="h-10"
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>
                        Your company or team. You&apos;ll be its owner.
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {formError && (
                <div
                  role="alert"
                  className="rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"
                >
                  {formError}
                </div>
              )}

              <Button
                type="submit"
                className="h-11 w-full"
                disabled={signup.isPending || (joining && !preview.data)}
              >
                {signup.isPending
                  ? "Creating your account…"
                  : joining
                    ? "Create account and join"
                    : "Create account"}
                <ArrowRight className="size-4" />
              </Button>
            </form>
          </Form>
        </div>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link
            to="/login"
            search={{ redirect: invite ? `/join/${invite}` : undefined }}
            className="font-medium text-primary hover:underline"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
