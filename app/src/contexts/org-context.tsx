import { createContext, useContext, type ReactNode } from "react";
import type { OrganizationResponse } from "@/api/model";

// The organization the current page is about, as the API resolved it for the
// signed-in user. Pages read the role from here to decide what to offer; the
// API enforces the same rules on every request regardless.
interface OrgContextValue {
  organization: OrganizationResponse;
  orgId: string;
  isManager: boolean;
}

const OrgContext = createContext<OrgContextValue | undefined>(undefined);

export function OrgProvider({
  organization,
  children,
}: {
  organization: OrganizationResponse;
  children: ReactNode;
}) {
  return (
    <OrgContext.Provider
      value={{
        organization,
        orgId: organization.id,
        isManager:
          organization.role === "owner" || organization.role === "admin",
      }}
    >
      {children}
    </OrgContext.Provider>
  );
}

export function useOrg(): OrgContextValue {
  const context = useContext(OrgContext);
  if (context === undefined) {
    throw new Error("useOrg must be used inside an organization route");
  }
  return context;
}

const LAST_ORG_KEY = "planstride.lastOrgId";

export function rememberOrg(orgId: string) {
  try {
    window.localStorage.setItem(LAST_ORG_KEY, orgId);
  } catch {
    // Storage can be unavailable (private mode); remembering is a nicety.
  }
}

export function lastOrg(): string | null {
  try {
    return window.localStorage.getItem(LAST_ORG_KEY);
  } catch {
    return null;
  }
}
