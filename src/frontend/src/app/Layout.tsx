import { ChevronsUpDownIcon, CircleUserIcon, LandmarkIcon, LanguagesIcon, LogOutIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { PageTransition } from "@/components/motion";
import { ThemeToggle } from "@/components/theme";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Breadcrumb, BreadcrumbItem, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupLabel, SidebarHeader, SidebarInset, SidebarMenu,
  SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarTrigger, useSidebar,
} from "@/components/ui/sidebar";
import { useLogout, useMe } from "@/features/auth/api";
import { isRtl } from "@/i18n";
import { CommandPalette, CommandTrigger } from "./CommandPalette";
import { NAV_GROUPS, type NavItem } from "./nav";
import { PeriodPicker } from "./filters";

export function Layout() {
  useTranslation();  // re-render on language change: the sidebar side must follow the text direction
  const rtl = isRtl();
  return (
    <SidebarProvider>
      <AppSidebar key={rtl ? "rtl" : "ltr"} side={rtl ? "right" : "left"} />
      <SidebarInset>
        <Header />
        <CommandPalette />
        <main className="flex flex-1 flex-col gap-4 p-4 pt-0">
          <Content />
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}

function Content() {
  const { pathname } = useLocation();
  return <PageTransition routeKey={pathname}><Outlet /></PageTransition>;
}

function Header() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const current = NAV_GROUPS.flatMap((g) => g.items).find((i) => i.to === pathname)?.key
    ?? (pathname === "/profile" ? "profile" : "dashboard");
  return (
    <header className="flex shrink-0 flex-wrap items-center gap-2 py-3 md:h-16 md:py-0">
      <div className="flex items-center gap-2 px-4">
        <SidebarTrigger className="-ms-1" />
        <Separator orientation="vertical" className="me-2 data-vertical:h-4 data-vertical:self-auto" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden md:block">{t("app.name")}</BreadcrumbItem>
            <BreadcrumbSeparator className="hidden md:block rtl:rotate-180" />
            <BreadcrumbItem><BreadcrumbPage>{t(`nav.${current}`)}</BreadcrumbPage></BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </div>
      <div className="ms-auto flex flex-wrap items-center gap-2 px-4">
        <PeriodPicker />
        <CommandTrigger />
        <ThemeToggle />
      </div>
    </header>
  );
}

function AppSidebar({ side }: { side: "left" | "right" }) {
  const { t } = useTranslation();
  const { data: me } = useMe();
  return (
    <Sidebar variant="inset" side={side} collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<NavLink to="/" />}>
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <LandmarkIcon className="size-4" />
              </div>
              <div className="grid flex-1 text-start text-sm leading-tight">
                <span className="truncate font-semibold">{t("app.name")}</span>
                <span className="truncate text-xs text-muted-foreground">{me?.merchant.display_name}</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        {NAV_GROUPS.map((g) => <NavGroup key={g.label} label={t(`shell.group.${g.label}`)} items={g.items} />)}
        <NavGroup className="mt-auto" items={[{ to: "/profile", key: "profile", icon: <CircleUserIcon /> }]} />
      </SidebarContent>
      <SidebarFooter><NavUser /></SidebarFooter>
    </Sidebar>
  );
}

function NavGroup({ label, items, className }: { label?: string; items: NavItem[]; className?: string }) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const { isMobile, setOpenMobile } = useSidebar();
  return (
    <SidebarGroup className={className}>
      {label && <SidebarGroupLabel>{label}</SidebarGroupLabel>}
      <SidebarMenu>
        {items.map((item) => (
          <SidebarMenuItem key={item.to}>
            <SidebarMenuButton isActive={pathname === item.to} tooltip={t(`nav.${item.key}`)}
              render={<NavLink to={item.to} end={item.to === "/"} onClick={() => isMobile && setOpenMobile(false)} />}>
              {item.icon}
              <span>{t(`nav.${item.key}`)}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  );
}

function initials(name: string | undefined) {
  return (name ?? "MP").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");
}

function NavUser() {
  const { t, i18n } = useTranslation();
  const { data: me } = useMe();
  const { isMobile } = useSidebar();
  const logout = useLogout();
  const navigate = useNavigate();
  const name = me?.merchant.display_name;
  const person = (
    <>
      <Avatar><AvatarFallback>{initials(name)}</AvatarFallback></Avatar>
      <div className="grid flex-1 text-start text-sm leading-tight">
        <span className="truncate font-medium">{name}</span>
        <span className="truncate text-xs">{me?.email}</span>
      </div>
    </>
  );
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger render={<SidebarMenuButton size="lg" className="aria-expanded:bg-muted" />}>
            {person}
            <ChevronsUpDownIcon className="ms-auto size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent className="min-w-56 rounded-lg" side={isMobile ? "bottom" : isRtl() ? "left" : "right"}
            align="end" sideOffset={4}>
            <DropdownMenuGroup>
              <DropdownMenuLabel className="p-0 font-normal">
                <div className="flex items-center gap-2 px-1 py-1.5 text-start text-sm">{person}</div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem onClick={() => navigate("/profile")}><CircleUserIcon />{t("nav.profile")}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => i18n.changeLanguage(i18n.language === "ar" ? "fr" : "ar")}>
                <LanguagesIcon />{i18n.language === "ar" ? "Français" : "العربية"}
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => logout.mutate(undefined, { onSettled: () => navigate("/login") })}>
              <LogOutIcon />{t("auth.logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
