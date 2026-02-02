import { createFileRoute, Navigate, Outlet, useLocation } from "@tanstack/react-router";
import { AppSidebar } from "@/components/sidebar/app-sidebar-new";
import { ContentLayout } from "@/components/layouts/content-layout";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Save } from "lucide-react";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import { useAuth } from "@/hooks/use-auth";

export const Route = createFileRoute("/_main")({
  component: ProtectedLayout,
});

function ProtectedLayout() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeSection, setActiveSection] = useState("general");

  // Update active section based on current path
  useEffect(() => {
    const path = location.pathname;
    const section = path.replace('/', '') || 'general';
    setActiveSection(section);
  }, [location.pathname]);

  // Show loading spinner while checking auth
  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }

  const handleSave = () => {
    // Here you would typically save to an API
    console.log("Saving configuration...");
    toast.success("Configuration saved successfully");
  };

  return (
    <div className="flex w-full">
      <AppSidebar
        activeSection={activeSection}
        onSectionChange={setActiveSection}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <ContentLayout fullHeight={false}>
        <div className="flex items-center justify-end mb-6">
          <Button onClick={handleSave} className="gap-2">
            <Save className="h-4 w-4" />
            Save Changes
          </Button>
        </div>
        <Outlet context={{ activeSection }} />
      </ContentLayout>
    </div>
  );
}
