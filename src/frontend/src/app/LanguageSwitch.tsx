import { useTranslation } from "react-i18next";

export function LanguageSwitch() {
  const { i18n } = useTranslation();
  const next = i18n.language === "ar" ? "fr" : "ar";
  return (
    <button onClick={() => i18n.changeLanguage(next)}
      className="rounded-lg border border-input bg-card px-2 py-1 text-sm text-foreground hover:bg-muted/50">
      {next === "ar" ? "العربية" : "Français"}
    </button>
  );
}
