import {
  ArrowLeftRightIcon, BellRingIcon, ChartAreaIcon, FlaskConicalIcon, GiftIcon, LayoutDashboardIcon, UsersIcon, WalletIcon,
} from "lucide-react";
import type { ReactNode } from "react";

export type NavItem = { to: string; key: string; icon: ReactNode };
export const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  { label: "operate", items: [
    { to: "/", key: "dashboard", icon: <LayoutDashboardIcon /> },
    { to: "/transactions", key: "transactions", icon: <ArrowLeftRightIcon /> },
    { to: "/collections", key: "collections", icon: <WalletIcon /> },
    { to: "/alerts", key: "alerts", icon: <BellRingIcon /> },
  ] },
  { label: "analyse", items: [
    { to: "/insights", key: "insights", icon: <ChartAreaIcon /> },
    { to: "/simulator", key: "simulator", icon: <FlaskConicalIcon /> },
  ] },
  { label: "customers", items: [
    { to: "/customers", key: "customers", icon: <UsersIcon /> },
    { to: "/loyalty", key: "loyalty", icon: <GiftIcon /> },
  ] },
];
