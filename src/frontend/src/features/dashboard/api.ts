import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Activity, Dashboard, Pulse } from "@/api/types";
import type { Filters } from "@/app/filters";

export const useDashboard = (f: Filters) =>
  useQuery({
    queryKey: ["dashboard", f],
    queryFn: () => api<Dashboard>("/analytics/dashboard", {
      query: { date_from: f.dateFrom, date_to: f.dateTo, granularity: f.granularity },
    }),
    placeholderData: keepPreviousData,
  });

export const useActivity = (f: Pick<Filters, "dateFrom" | "dateTo">) =>
  useQuery({
    queryKey: ["activity", f.dateFrom, f.dateTo],
    queryFn: () => api<Activity>("/analytics/activity", { query: { date_from: f.dateFrom, date_to: f.dateTo } }),
    placeholderData: keepPreviousData,
  });

export const usePulse = (f: Pick<Filters, "dateFrom" | "dateTo">) =>
  useQuery({
    queryKey: ["pulse", f.dateFrom, f.dateTo],
    queryFn: () => api<Pulse>("/insights/pulse", { query: { date_from: f.dateFrom, date_to: f.dateTo } }),
    placeholderData: keepPreviousData,
  });
