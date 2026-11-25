import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type {
  LoyaltyAccrual, LoyaltyLedger, LoyaltyProgram, LoyaltyProgramState, LoyaltyRulesIn, LoyaltySimulation,
  LoyaltySimulationIn,
} from "@/api/types";

const KEY = ["loyalty"] as const;

export const useLoyaltyProgram = () =>
  useQuery({ queryKey: [...KEY, "program"], queryFn: () => api<LoyaltyProgramState>("/loyalty/program") });

export const useSaveProgram = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { rules: LoyaltyRulesIn; effective_from: string }) =>
      api<LoyaltyProgram>("/loyalty/program", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
};

export const useLoyaltySimulation = () =>
  useMutation({
    mutationFn: (body: LoyaltySimulationIn) =>
      api<LoyaltySimulation>("/loyalty/simulations", { method: "POST", body: JSON.stringify(body) }),
  });

export const useLedger = () =>
  useQuery({ queryKey: [...KEY, "ledger"], queryFn: () => api<LoyaltyLedger>("/loyalty/ledger", { query: { size: 15 } }) });

export const useAccrue = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<LoyaltyAccrual>("/loyalty/ledger/accrue", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...KEY, "ledger"] }),
  });
};
