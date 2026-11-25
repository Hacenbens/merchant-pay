import { EyeIcon, EyeOffIcon, LandmarkIcon, LoaderCircleIcon, LockIcon, MailIcon } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { ApiError } from "@/api/client";
import { containerVariants, itemVariants, motion } from "@/components/motion";
import { ThemeToggle } from "@/components/theme";
import { Button } from "@/components/ui/button";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import { useLogin } from "./api";

/** Sign-in, laid out like shadcn-fintech's: dark brand panel + staggered form. */
export function LoginPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    login.mutate({ email, password }, { onSuccess: () => navigate("/", { replace: true }) });
  };

  return (
    <div className="flex min-h-svh">
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-zinc-950 lg:flex">
        <div className="relative z-20 flex items-center gap-2.5 p-8">
          <div className="flex size-8 items-center justify-center rounded-lg bg-white text-black">
            <LandmarkIcon className="size-4" />
          </div>
          <span className="text-sm font-semibold text-white">{t("app.name")}</span>
        </div>
        <div className="absolute inset-0 flex items-center justify-center"><NetworkMotif /></div>
        <div className="relative z-20 mt-auto p-8">
          <div className="rounded-xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
            <p className="text-sm leading-relaxed text-white/80">{t("app.tagline")}</p>
            <p className="mt-3 text-xs text-white/50">{t("auth.context")}</p>
          </div>
        </div>
      </div>

      <div className="relative flex flex-1 items-center justify-center bg-background px-6 py-12">
        <div className="absolute end-4 top-4 flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={() => i18n.changeLanguage(i18n.language === "ar" ? "fr" : "ar")}>
            {i18n.language === "ar" ? "Français" : "العربية"}
          </Button>
          <ThemeToggle />
        </div>
        <motion.div className="w-full max-w-sm" variants={containerVariants} initial="hidden" animate="visible">
          <motion.div className="mb-8 flex flex-col items-center lg:hidden" variants={itemVariants}>
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <LandmarkIcon className="size-5" />
            </div>
          </motion.div>
          <motion.div className="text-center" variants={itemVariants}>
            <h1 className="text-2xl font-semibold tracking-tight">{t("auth.welcome")}</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">{t("auth.title")}</p>
          </motion.div>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <motion.div variants={itemVariants}>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium">{t("auth.email")}</label>
              <InputGroup>
                <InputGroupAddon align="inline-start"><MailIcon className="size-4 text-muted-foreground" /></InputGroupAddon>
                <InputGroupInput id="email" type="email" autoComplete="username" required value={email}
                  placeholder="nom@commerce.dz" onChange={(e) => setEmail(e.target.value)} />
              </InputGroup>
            </motion.div>
            <motion.div variants={itemVariants}>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium">{t("auth.password")}</label>
              <InputGroup>
                <InputGroupAddon align="inline-start"><LockIcon className="size-4 text-muted-foreground" /></InputGroupAddon>
                <InputGroupInput id="password" type={show ? "text" : "password"} autoComplete="current-password" required
                  value={password} onChange={(e) => setPassword(e.target.value)} />
                <InputGroupAddon align="inline-end">
                  <InputGroupButton size="icon-xs" aria-label={t(show ? "auth.hidePassword" : "auth.showPassword")}
                    onClick={() => setShow((s) => !s)}>
                    {show ? <EyeOffIcon /> : <EyeIcon />}
                  </InputGroupButton>
                </InputGroupAddon>
              </InputGroup>
            </motion.div>
            {login.isError && (
              <motion.p role="alert" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {login.error instanceof ApiError && login.error.status === 429 ? t("auth.throttled") : t("auth.error")}
              </motion.p>
            )}
            <motion.div variants={itemVariants}>
              <Button type="submit" size="lg" className="w-full" disabled={login.isPending}>
                {login.isPending && <LoaderCircleIcon className="animate-spin" />}
                {t("auth.submit")}
              </Button>
            </motion.div>
          </form>
          <motion.p variants={itemVariants} className="mt-6 text-center text-xs text-muted-foreground">
            {t("auth.demoHint")}
          </motion.p>
        </motion.div>
      </div>
    </div>
  );
}

/** Animated payment-network motif (stands in for the reference's 3D globe; SVG + motion only). */
function NetworkMotif() {
  const nodes = [[200, 70], [330, 150], [330, 290], [200, 370], [70, 290], [70, 150]];
  return (
    <svg viewBox="0 0 400 440" className="h-[70%] max-h-[560px] w-auto opacity-80" aria-hidden>
      {[60, 110, 160].map((r, i) => (
        <motion.circle key={r} cx="200" cy="220" r={r} fill="none" stroke="white" strokeOpacity={0.08 + i * 0.02}
          strokeDasharray="2 6" initial={{ pathLength: 0, rotate: 0 }} animate={{ pathLength: 1, rotate: i % 2 ? -360 : 360 }}
          transition={{ pathLength: { duration: 1.2, delay: i * 0.2 }, rotate: { duration: 60 + i * 20, repeat: Infinity, ease: "linear" } }}
          style={{ transformOrigin: "200px 220px" }} />
      ))}
      {nodes.map(([x, y], i) => (
        <g key={i}>
          <motion.line x1="200" y1="220" x2={x} y2={y} stroke="white" strokeOpacity={0.15} strokeWidth={1}
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 0.6 + i * 0.08, duration: 0.6 }} />
          <motion.circle cx={x} cy={y} r="5" fill="white" fillOpacity={0.7}
            initial={{ scale: 0 }} animate={{ scale: [0, 1.3, 1] }} transition={{ delay: 1 + i * 0.08 }} />
          <motion.circle r="2.5" fill="white" cx={200} cy={220} initial={{ cx: 200, cy: 220, opacity: 0 }}
            animate={{ cx: [200, x], cy: [220, y], opacity: [0, 1, 0] }}
            transition={{ duration: 2.4, delay: 1.5 + i * 0.4, repeat: Infinity, repeatDelay: 1.2, ease: "easeInOut" }} />
        </g>
      ))}
      <motion.rect x="182" y="202" width="36" height="36" rx="10" fill="white"
        initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 300, damping: 20, delay: 0.2 }}
        style={{ transformOrigin: "200px 220px" }} />
    </svg>
  );
}
