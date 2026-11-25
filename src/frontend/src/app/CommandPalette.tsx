import { CalendarRangeIcon, CircleUserIcon, LanguagesIcon, LogOutIcon, MonitorIcon, MoonIcon, SunIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { useTheme } from "@/components/theme";
import {
  Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator,
} from "@/components/ui/command";
import { useLogout } from "@/features/auth/api";
import { useFilters } from "./filters";
import { NAV_GROUPS } from "./nav";

const OPEN_EVENT = "mp:command-palette";

/** ⌘K / Ctrl+K: jump to a page, change the period, theme or language, or log out. */
export function CommandPalette() {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { setTheme } = useTheme();
  const { setLastDays } = useFilters();
  const logout = useLogout();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    const fromButton = () => setOpen(true);
    document.addEventListener("keydown", down);
    window.addEventListener(OPEN_EVENT, fromButton);
    return () => {
      document.removeEventListener("keydown", down);
      window.removeEventListener(OPEN_EVENT, fromButton);
    };
  }, []);

  const run = useCallback((fn: () => void) => { setOpen(false); fn(); }, []);
  const item = "gap-2";

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title={t("shell.palette")} description={t("shell.paletteHelp")}>
      <Command>
        <CommandInput placeholder={t("shell.search")} />
        <CommandList>
          <CommandEmpty>{t("shell.noResults")}</CommandEmpty>
          <CommandGroup heading={t("shell.pages")}>
            {[...NAV_GROUPS.flatMap((g) => g.items), { to: "/profile", key: "profile", icon: <CircleUserIcon /> }].map((p) => (
              <CommandItem key={p.to} className={item} onSelect={() => run(() => navigate(p.to))}>
                <span className="[&_svg]:size-4">{p.icon}</span>{t(`nav.${p.key}`)}
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading={t("shell.period")}>
            {[7, 30, 90].map((n) => (
              <CommandItem key={n} className={item} onSelect={() => run(() => setLastDays(n))}>
                <CalendarRangeIcon className="size-4" />{t("shell.lastDays", { n })}
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading={t("shell.preferences")}>
            <CommandItem className={item} onSelect={() => run(() => setTheme("light"))}><SunIcon className="size-4" />{t("shell.theme.light")}</CommandItem>
            <CommandItem className={item} onSelect={() => run(() => setTheme("dark"))}><MoonIcon className="size-4" />{t("shell.theme.dark")}</CommandItem>
            <CommandItem className={item} onSelect={() => run(() => setTheme("system"))}><MonitorIcon className="size-4" />{t("shell.theme.system")}</CommandItem>
            <CommandItem className={item} onSelect={() => run(() => i18n.changeLanguage(i18n.language === "ar" ? "fr" : "ar"))}>
              <LanguagesIcon className="size-4" />{i18n.language === "ar" ? "Français" : "العربية"}
            </CommandItem>
            <CommandItem className={item} onSelect={() => run(() => logout.mutate(undefined, { onSettled: () => navigate("/login") }))}>
              <LogOutIcon className="size-4" />{t("auth.logout")}
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  );
}

/** The ⌘K hint in the header (clickable, unlike the reference's decorative kbd, for touch users). */
export function CommandTrigger() {
  const { t } = useTranslation();
  const mac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
  return (
    <button type="button" onClick={() => window.dispatchEvent(new Event(OPEN_EVENT))} aria-label={t("shell.palette")}
      className="hidden h-6 select-none items-center gap-1 rounded border bg-muted px-2 font-mono text-[10px] font-medium text-muted-foreground transition-colors hover:text-foreground sm:flex">
      <span className="text-xs">{mac ? "⌘" : "Ctrl"}</span>K
    </button>
  );
}
