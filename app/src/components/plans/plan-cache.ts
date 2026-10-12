import { useQueryClient } from "@tanstack/react-query";
import {
  getMyPlanListQueryKey,
  getMyWeekGetQueryKey,
  getPlanGetQueryKey,
} from "@/api/endpoints/plans/plans";
import { getReviewQueueQueryKey } from "@/api/endpoints/reviews/reviews";
import type { MyWeekResponse, PlanResponse } from "@/api/model";

// After any change to a plan, every view of it agrees: the plan page and "my
// week" take the server's copy directly; lists that summarize plans refetch.
export function useSyncPlan(orgId: string) {
  const queryClient = useQueryClient();
  return (plan: PlanResponse) => {
    queryClient.setQueryData(getPlanGetQueryKey(orgId, plan.id), plan);
    queryClient.setQueryData<MyWeekResponse>(
      getMyWeekGetQueryKey(orgId, plan.week_start),
      (old) => (old && old.plan?.id === plan.id ? { ...old, plan } : old)
    );
    void queryClient.invalidateQueries({
      queryKey: getReviewQueueQueryKey(orgId),
    });
    void queryClient.invalidateQueries({
      queryKey: getMyPlanListQueryKey(orgId),
    });
    const teamPrefix = `/organizations/${orgId}/teams/`;
    void queryClient.invalidateQueries({
      predicate: (query) =>
        typeof query.queryKey[0] === "string" &&
        query.queryKey[0].startsWith(teamPrefix),
    });
  };
}
