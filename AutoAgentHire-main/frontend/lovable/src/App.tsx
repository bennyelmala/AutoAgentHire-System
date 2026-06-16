import AutomationPage from "./pages/Automation";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import Signup from "./pages/Signup";
import Login from "./pages/Login";
import OnboardingIntegrated from "./pages/OnboardingIntegrated";
import { DashboardLayout } from "./components/layout/DashboardLayout";
import DashboardHome from "./pages/dashboard/DashboardHome";
import JobSearchConfig from "./pages/dashboard/JobSearchConfig";
import Applications from "./pages/dashboard/Applications";
import { ApiKeySettings } from "./components/ApiKeySettings";
import RecommendedJobs from "./components/RecommendedJobs";
import ATSChecker from "@/pages/ATSChecker";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/login" element={<Login />} />
          <Route path="/onboarding" element={<OnboardingIntegrated />} />
          <Route path="/ats-checker" element={<ATSChecker />} />
          <Route path="/dashboard" element={<DashboardLayout />}>
            <Route index element={<DashboardHome />} />
            <Route path="search" element={<JobSearchConfig />} />
            <Route path="recommended" element={<RecommendedJobs />} />
            <Route path="applications" element={<Applications />} />
            <Route path="automation" element={<AutomationPage />} />
            <Route path="resume" element={<DashboardHome />} />
            <Route path="settings" element={<ApiKeySettings />} />
            <Route path="help" element={<DashboardHome />} />
            <Route path="ats" element={<ATSChecker />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
