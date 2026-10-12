import { createFileRoute } from "@tanstack/react-router";
import {
  ArrowRight,
  CalendarCheck,
  ClipboardCheck,
  EyeOff,
  Flag,
  History,
  Lock,
  Megaphone,
  PenLine,
  Repeat,
  Scale,
  ShieldCheck,
  Sparkles,
  Target,
  Wand2,
  CircleHelp,
} from "lucide-react";
import { Logo, Logomark } from "@/components/logo";
import {
  PlanCard,
  ReviewDemo,
  TeamWeekMock,
} from "@/components/landing/product-mocks";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { buttonVariants } from "@/components/ui/button";
import { LOGIN_URL, SIGNUP_URL } from "@/lib/links";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({ component: Home });

const STEPS = [
  {
    icon: PenLine,
    when: "Monday",
    title: "Write the plan",
    body: "One main task and why it matters, the sub-goals that get it over the line, and how users will hear about it. Paste messy notes and PlanStride drafts it for you.",
  },
  {
    icon: ClipboardCheck,
    when: "Monday",
    title: "Get it approved",
    body: "The AI reviewer flags tasks you couldn't honestly tick off before your lead sees them. Your lead approves, or sends it back with a comment.",
  },
  {
    icon: Flag,
    when: "Friday",
    title: "Ship it, then close the week",
    body: "Tick tasks off as they land. On Friday, close the week: did the main task ship? Your history shows the team's real rhythm, not the one in the roadmap.",
  },
];

const FLAGS = [
  {
    icon: Target,
    title: "Work, not results",
    body: "“Implement checkout” can't be ticked off honestly.",
  },
  {
    icon: CircleHelp,
    title: "No reason given",
    body: "A main task that doesn't say why it matters.",
  },
  {
    icon: Megaphone,
    title: "Nobody will hear about it",
    body: "No changelog, announcement or analytics goal.",
  },
  {
    icon: Scale,
    title: "Too big for a week",
    body: "Scope that won't ship by Friday, with a smaller slice that will.",
  },
  {
    icon: Repeat,
    title: "Carried over, again",
    body: "Work that didn't finish last week, checked against your last two plans.",
  },
];

const LEAD_POINTS = [
  {
    icon: CalendarCheck,
    title: "The week at a glance",
    body: "Who submitted, what's approved, tasks done, and whether each main task shipped.",
  },
  {
    icon: ClipboardCheck,
    title: "One review queue",
    body: "Every plan waiting for you across the teams you lead. Approve, or send it back with a note.",
  },
  {
    icon: History,
    title: "A history that's honest",
    body: "Week by week: how many plans shipped their main task. Spot the pattern before the retro.",
  },
];

const TRUST = [
  {
    icon: Lock,
    body: "Every organization's data is walled off in the API itself, not just hidden in the interface.",
  },
  {
    icon: EyeOff,
    body: "Drafts are private until you submit. Then your teammates, your lead, and your organization's admins can read them.",
  },
  {
    icon: ShieldCheck,
    body: "PlanStride staff see accounts and usage, never what's in your plans.",
  },
  {
    icon: Sparkles,
    body: "AI reviews run on Google's Gemini. PlanStride logs that a call happened, not what it said.",
  },
];

const FAQ = [
  {
    q: "Does PlanStride replace Linear or Jira?",
    a: "No. Your tracker holds the backlog and the tickets. PlanStride holds the one thing each engineer commits to ship this week, and whether it shipped. Plenty of teams paste ticket links into their sub-goals.",
  },
  {
    q: "Who can see my plan?",
    a: "While it's a draft, only you. Once you submit it: the people on your teams, your team lead, and your organization's owners and admins. Nobody outside your organization, PlanStride staff included.",
  },
  {
    q: "What if the AI is busy or down?",
    a: "You can always write, save and submit a plan without it. If the AI is slow or rate-limited, PlanStride says so in plain words and leaves your plan exactly as it was.",
  },
  {
    q: "Who approves a team lead's own plan?",
    a: "The lead of another team they're on, for example an “Engineering leads” team run by your CTO. Nobody approves their own plan.",
  },
  {
    q: "How long does setup take?",
    a: "Create your account and organization, share an invite link, set up a team with a lead. Your team can plan the same morning.",
  },
];

function Home() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main>
        <Hero />
        <Positioning />
        <HowItWorks />
        <AiSection />
        <ForLeads />
        <Trust />
        <Faq />
        <FinalCta />
      </main>
      <SiteFooter />
    </div>
  );
}

function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-transparent bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <a href="#top" aria-label="PlanStride home">
          <Logo className="h-7" />
        </a>
        <nav
          className="hidden items-center gap-6 text-sm text-muted-foreground md:flex"
          aria-label="Sections"
        >
          <a className="hover:text-foreground" href="#how-it-works">
            How it works
          </a>
          <a className="hover:text-foreground" href="#ai-review">
            AI review
          </a>
          <a className="hover:text-foreground" href="#for-leads">
            For team leads
          </a>
          <a className="hover:text-foreground" href="#faq">
            FAQ
          </a>
        </nav>
        <div className="flex items-center gap-2">
          <a
            className={buttonVariants({
              variant: "ghost",
              className: "hidden sm:inline-flex",
            })}
            href={LOGIN_URL}
          >
            Sign in
          </a>
          <a className={buttonVariants()} href={SIGNUP_URL}>
            Get started
          </a>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section id="top" className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[620px] [mask-image:radial-gradient(ellipse_70%_90%_at_50%_0%,black,transparent)]"
      >
        <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--color-border)_1px,transparent_1px),linear-gradient(to_bottom,var(--color-border)_1px,transparent_1px)] bg-[size:48px_48px] opacity-70" />
      </div>
      <div className="mx-auto grid grid-cols-1 max-w-6xl items-center gap-12 px-4 pt-14 pb-20 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:pt-20 lg:pb-28">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border bg-background/70 px-3 py-1 text-xs font-medium text-muted-foreground">
            <Logomark className="size-3.5" /> Weekly planning for engineering
            teams
          </p>
          <h1 className="mt-6 text-5xl font-semibold tracking-tight text-balance sm:text-6xl lg:text-7xl">
            Monday plans.
            <span className="block text-primary">Friday results.</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg text-pretty text-muted-foreground">
            Each engineer commits to one thing they&apos;ll ship by Friday.
            PlanStride pushes back on vague tasks before the plan reaches you,
            then shows the whole team&apos;s week on one screen.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <a
              className={buttonVariants({
                size: "lg",
                className: "h-11 px-5 text-sm",
              })}
              href={SIGNUP_URL}
            >
              Get started <ArrowRight className="size-4" />
            </a>
            <a
              className={buttonVariants({
                size: "lg",
                variant: "outline",
                className: "h-11 px-5 text-sm",
              })}
              href="#how-it-works"
            >
              See how it works
            </a>
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            Sign up with your email, then bring your team in with an invite
            link.
          </p>
        </div>
        <div className="lg:pl-6">
          <PlanCard />
        </div>
      </div>
    </section>
  );
}

function Positioning() {
  return (
    <section className="border-y bg-muted/40">
      <div className="mx-auto max-w-4xl px-4 py-12 text-center sm:px-6">
        <p className="text-xl font-medium text-balance sm:text-2xl">
          Your tracker shows what&apos;s in progress. PlanStride shows what each
          engineer promised to ship this week, and whether they did.
        </p>
      </div>
    </section>
  );
}

function SectionIntro({
  eyebrow,
  title,
  body,
  className,
}: {
  eyebrow: string;
  title: string;
  body: string;
  className?: string;
}) {
  return (
    <div className={cn("max-w-2xl", className)}>
      <p className="text-sm font-medium text-primary">{eyebrow}</p>
      <h2 className="mt-2 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        {title}
      </h2>
      <p className="mt-4 text-lg text-pretty text-muted-foreground">{body}</p>
    </div>
  );
}

function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:py-28">
        <SectionIntro
          eyebrow="How it works"
          title="One plan a week. One thing that ships."
          body="The rhythm is the product: write the plan on Monday, get it approved, track it through the week and close it out on Friday."
        />
        <ol className="mt-12 grid gap-4 md:grid-cols-3">
          {STEPS.map(({ icon: Icon, when, title, body }, index) => (
            <li key={title} className="rounded-2xl border bg-background p-6">
              <div className="flex items-center justify-between">
                <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Icon className="size-5" />
                </span>
                <span className="text-xs font-medium text-muted-foreground">
                  {index + 1} · {when}
                </span>
              </div>
              <h3 className="mt-5 text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {body}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function AiSection() {
  return (
    <section id="ai-review" className="scroll-mt-20 border-y bg-muted/40">
      <div className="mx-auto grid grid-cols-1 max-w-6xl items-start gap-12 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:py-28">
        <div>
          <SectionIntro
            eyebrow="AI review"
            title="The approval meeting, before the meeting."
            body="Ask for a review and PlanStride reads your plan the way a demanding lead would. Every finding points at a task and comes with a rewrite you can apply in one click."
          />
          <ul className="mt-8 space-y-4">
            {FLAGS.map(({ icon: Icon, title, body }) => (
              <li key={title} className="flex gap-3">
                <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg border bg-background text-amber-600">
                  <Icon className="size-4" />
                </span>
                <span>
                  <span className="block font-medium">{title}</span>
                  <span className="block text-sm text-muted-foreground">
                    {body}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-8 flex gap-3 rounded-xl border bg-background p-4 text-sm">
            <Wand2 className="mt-0.5 size-4 shrink-0 text-primary" />
            <p className="text-muted-foreground">
              <span className="font-medium text-foreground">
                Or start from a brain dump.
              </span>{" "}
              Paste &ldquo;need to finish the billing page, probably also fix
              that webhook bug, should announce it in the changelog&rdquo; and
              get a structured draft to edit. Nothing is saved until you say so.
            </p>
          </div>
        </div>
        <div className="lg:sticky lg:top-24">
          <ReviewDemo />
          <p className="mt-3 text-center text-xs text-muted-foreground">
            This example is live: click &ldquo;Use this wording&rdquo;.
          </p>
        </div>
      </div>
    </section>
  );
}

function ForLeads() {
  return (
    <section id="for-leads" className="scroll-mt-20">
      <div className="mx-auto grid grid-cols-1 max-w-6xl items-center gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[1fr_1.05fr] lg:py-28">
        <div className="order-2 lg:order-1">
          <TeamWeekMock />
        </div>
        <div className="order-1 lg:order-2">
          <SectionIntro
            eyebrow="For team leads"
            title="Your team's week on one screen."
            body="Know on Wednesday which plan is slipping, not on Friday. Approve plans from one queue and see whether the week actually shipped."
          />
          <ul className="mt-8 space-y-5">
            {LEAD_POINTS.map(({ icon: Icon, title, body }) => (
              <li key={title} className="flex gap-3">
                <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="size-4" />
                </span>
                <span>
                  <span className="block font-medium">{title}</span>
                  <span className="block text-sm text-muted-foreground">
                    {body}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function Trust() {
  return (
    <section className="border-y bg-zinc-950 text-zinc-50">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-medium text-emerald-400">
            Privacy by design
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            Your plans stay your team&apos;s.
          </h2>
        </div>
        <ul className="mt-10 grid gap-6 sm:grid-cols-2">
          {TRUST.map(({ icon: Icon, body }) => (
            <li key={body} className="flex gap-3">
              <Icon className="mt-0.5 size-5 shrink-0 text-emerald-400" />
              <p className="text-zinc-300">{body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Faq() {
  return (
    <section id="faq" className="scroll-mt-20">
      <div className="mx-auto max-w-3xl px-4 py-20 sm:px-6 lg:py-28">
        <h2 className="text-3xl font-semibold tracking-tight">
          Questions teams ask
        </h2>
        <Accordion className="mt-8">
          {FAQ.map(({ q, a }) => (
            <AccordionItem key={q} value={q}>
              <AccordionTrigger className="py-4 text-base">
                {q}
              </AccordionTrigger>
              <AccordionContent className="pb-4 text-muted-foreground">
                {a}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="px-4 pb-20 sm:px-6">
      <div className="mx-auto max-w-6xl overflow-hidden rounded-3xl bg-primary px-6 py-14 text-center text-primary-foreground sm:px-12">
        <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          Plan next week in five minutes.
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-pretty text-primary-foreground/85">
          Create your organization, invite your team with a link, and have
          Monday&apos;s plans approved by lunch.
        </p>
        <a
          href={SIGNUP_URL}
          className="mt-8 inline-flex h-11 items-center gap-2 rounded-lg bg-background px-5 text-sm font-medium text-foreground transition-colors hover:bg-background/90"
        >
          Get started <ArrowRight className="size-4" />
        </a>
      </div>
    </section>
  );
}

function SiteFooter() {
  return (
    <footer className="border-t">
      <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:px-6">
        <div className="flex items-center gap-3">
          <Logomark className="size-6" />
          <span>Weekly planning for engineering teams.</span>
        </div>
        <div className="flex items-center gap-5">
          <a className="hover:text-foreground" href={LOGIN_URL}>
            Sign in
          </a>
          <a className="hover:text-foreground" href={SIGNUP_URL}>
            Get started
          </a>
          <span>© {new Date().getFullYear()} PlanStride</span>
        </div>
      </div>
    </footer>
  );
}
