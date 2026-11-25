import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Me, MerchantPatch, MerchantProfile } from "@/api/types";

export const useMe = () =>
  useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/merchant/me"), retry: false, staleTime: 5 * 60_000 });

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api<void>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>("/auth/logout", { method: "POST" }),
    onSettled: () => qc.clear(),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MerchantPatch) =>
      api<MerchantProfile>("/merchant/me", { method: "PATCH", body: JSON.stringify(body) }),
    // the goal feeds the GOAL_REACHED alert and the dashboard: refresh everything merchant-scoped
    onSuccess: () => qc.invalidateQueries(),
  });
}
