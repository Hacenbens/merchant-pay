import { createBrowserRouter, Navigate } from "react-router";
import { AlertsPage } from "@/features/alerts/AlertsPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { CollectionsPage } from "@/features/collections/CollectionsPage";
import { CustomersPage } from "@/features/customers/CustomersPage";
import { LoyaltyPage } from "@/features/loyalty/LoyaltyPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { InsightsPage } from "@/features/insights/InsightsPage";
import { ProfilePage } from "@/features/merchant/ProfilePage";
import { SimulatorPage } from "@/features/simulator/SimulatorPage";
import { TransactionsPage } from "@/features/transactions/TransactionsPage";
import { FilterProvider } from "./filters";
import { Layout } from "./Layout";
import { RequireAuth } from "./RequireAuth";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth><FilterProvider><Layout /></FilterProvider></RequireAuth>,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "transactions", element: <TransactionsPage /> },
      { path: "collections", element: <CollectionsPage /> },
      { path: "alerts", element: <AlertsPage /> },
      { path: "simulator", element: <SimulatorPage /> },
      { path: "insights", element: <InsightsPage /> },
      { path: "customers", element: <CustomersPage /> },
      { path: "loyalty", element: <LoyaltyPage /> },
      { path: "profile", element: <ProfilePage /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
