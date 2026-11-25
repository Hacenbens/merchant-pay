import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import { router } from "./app/router";
import { MotionProvider } from "./components/motion";
import { ThemeProvider } from "./components/theme";
import { TooltipProvider } from "./components/ui/tooltip";
import "./i18n";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./index.css";

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MotionProvider>
          <TooltipProvider>
            <RouterProvider router={router} />
          </TooltipProvider>
        </MotionProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
