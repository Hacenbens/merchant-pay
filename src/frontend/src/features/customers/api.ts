import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type {
  CustomerDetail, CustomerOverview, CustomerPage, Decision, Reengagement, ReturnStatus, Segment,
} from "@/api/types";
import type { Filters } from "@/app/filters";

const KEY = ["customers"] as const;

export const useCustomerOverview = (windowDays: number, f: Pick<Filters, "dateFrom" | "dateTo">) =>
  useQuery({
    queryKey: [...KEY, "overview", windowDays, f.dateFrom, f.dateTo],
    queryFn: () => api<CustomerOverview>("/customers/overview", {
      query: { window_days: windowDays, date_from: f.dateFrom, date_to: f.dateTo },
    }),
    placeholderData: keepPreviousData,
  });

export type CustomerQuery = {
  windowDays: number; segment?: Segment; status?: ReturnStatus; highValue?: boolean; page: number;
};

export const useCustomers = (q: CustomerQuery) =>
  useQuery({
    queryKey: [...KEY, "list", q],
    queryFn: () => api<CustomerPage>("/customers", {
      query: { window_days: q.windowDays, segment: q.segment, status: q.status,
        high_value: q.highValue, page: q.page, size: 25 },
    }),
    placeholderData: keepPreviousData,
  });

export const useCustomer = (token: string | null, windowDays: number) =>
  useQuery({
    queryKey: [...KEY, "detail", token, windowDays],
    queryFn: () => api<CustomerDetail>(`/customers/${encodeURIComponent(token!)}`, {
      query: { window_days: windowDays },
    }),
    enabled: !!token,
  });

export const useReengagement = (windowDays: number, includeHidden: boolean) =>
  useQuery({
    queryKey: [...KEY, "reengagement", windowDays, includeHidden],
    queryFn: () => api<Reengagement>("/customers/reengagement", {
      query: { window_days: windowDays, include_hidden: includeHidden },
    }),
    placeholderData: keepPreviousData,
  });

export const useRecordDecision = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ token, decision, snoozeUntil }: { token: string; decision: Decision; snoozeUntil?: string }) =>
      api(`/customers/${encodeURIComponent(token)}/decisions`, {
        method: "POST", body: JSON.stringify({ decision, snooze_until: snoozeUntil ?? null }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
};
