import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useNavigate } from "react-router";
import { useLogout, useMe } from "@/features/auth/api";
import { PeriodPicker } from "./filters";
import { LanguageSwitch } from "./LanguageSwitch";

const NAV = [
  { to: "/", key: "dashboard" },
  { to: "/transactions", key: "transactions" },
  { to: "/collections", key: "collections" },
  { to: "/alerts", key: "alerts" },
  { to: "/simulator", key: "simulator" },
  { to: "/insights", key: "insights" },
  { to: "/customers", key: "customers" },
  { to: "/loyalty", key: "loyalty" },
  { to: "/profile", key: "profile" },
] as const;

export function Layout() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen md:grid md:grid-cols-[14rem_1fr]">
      <aside className="border-e border-slate-200 bg-white p-4 md:min-h-screen">
        <p className="text-lg font-bold text-brand-900">{t("app.name")}</p>
        <p className="mb-4 truncate text-xs text-slate-500">{me?.merchant.display_name}</p>
        <nav className="flex gap-1 overflow-x-auto md:flex-col">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}
              className={({ isActive }) => clsx(
                "whitespace-nowrap rounded-lg px-3 py-2 text-sm",
                isActive ? "bg-brand-50 font-semibold text-brand-700" : "text-slate-600 hover:bg-slate-100",
              )}>
              {t(`nav.${n.key}`)}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="min-w-0">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3">
          <PeriodPicker />
          <div className="flex items-center gap-2">
            <LanguageSwitch />
            <button className="text-sm text-slate-600 hover:underline"
              onClick={() => logout.mutate(undefined, { onSettled: () => navigate("/login") })}>
              {t("auth.logout")}
            </button>
          </div>
        </header>
        <main className="p-4 md:p-6"><Outlet /></main>
      </div>
    </div>
  );
}
