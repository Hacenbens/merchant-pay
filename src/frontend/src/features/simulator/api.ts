import { useMutation } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { ScenarioLab, ScenarioLabIn, Simulation } from "@/api/types";

export type SimulationInput = {
  baselineFrom: string;
  baselineTo: string;
  volumeGrowth: number;
  acceptanceChange: number; // absolute points, e.g. 0.02
  ticketChange: number; // relative, e.g. 0.05
};

export const useSimulation = () =>
  useMutation({
    mutationFn: (i: SimulationInput) =>
      api<Simulation>("/simulations/growth", {
        method: "POST",
        body: JSON.stringify({
          baseline_from: i.baselineFrom,
          baseline_to: i.baselineTo,
          volume_growth: i.volumeGrowth,
          acceptance_change: i.acceptanceChange,
          ticket_change: i.ticketChange,
        }),
      }),
  });

export const useScenarioLab = () =>
  useMutation({
    mutationFn: (body: ScenarioLabIn) =>
      api<ScenarioLab>("/simulations/lab", { method: "POST", body: JSON.stringify(body) }),
  });
