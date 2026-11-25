import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { ApiError } from "@/api/client";
import { LanguageSwitch } from "@/app/LanguageSwitch";
import { Button } from "@/components/ui";
import { useLogin } from "./api";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    login.mutate({ email, password }, { onSuccess: () => navigate("/", { replace: true }) });
  };
  const input = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none";

  return (
    <main className="grid min-h-screen place-items-center bg-gradient-to-br from-brand-50 to-slate-100 p-4">
      <div className="w-full max-w-sm">
        <div className="mb-4 flex justify-end"><LanguageSwitch /></div>
        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div>
            <h1 className="text-2xl font-bold text-brand-900">{t("app.name")}</h1>
            <p className="text-sm text-slate-500">{t("auth.title")}</p>
          </div>
          <label className="block text-sm font-medium text-slate-700">{t("auth.email")}
            <input className={input} type="email" autoComplete="username" required value={email}
              onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="block text-sm font-medium text-slate-700">{t("auth.password")}
            <input className={input} type="password" autoComplete="current-password" required value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </label>
          {login.isError && (
            <p role="alert" className="text-sm text-rose-600">
              {login.error instanceof ApiError && login.error.status === 429 ? t("auth.throttled") : t("auth.error")}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={login.isPending}>{t("auth.submit")}</Button>
          <p className="text-center text-xs text-slate-400">{t("auth.demoHint")}</p>
        </form>
      </div>
    </main>
  );
}
