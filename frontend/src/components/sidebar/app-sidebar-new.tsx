"use client";
import { cn } from "@/lib/utils";
import { useNavigate } from "@tanstack/react-router";
import {
  Bot,
  Brain,
  Database,
  Settings,
  Shield,
  Timer,
  Users,
  X,
} from "lucide-react";
import { NavUser } from "@/components/sidebar/nav-user";

interface AppSidebarProps {
  activeSection: string;
  onSectionChange: (section: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

const navItems = [
  { id: "general", label: "General", icon: Settings, path: "/general" },
  { id: "ai", label: "AI Configuration", icon: Brain, path: "/ai" },
  { id: "users", label: "User Mappings", icon: Users, path: "/users" },
  { id: "cooldowns", label: "Cooldowns", icon: Timer, path: "/cooldowns" },
  { id: "database", label: "Database", icon: Database, path: "/database" },
  { id: "moderation", label: "Moderation", icon: Shield, path: "/moderation" },
  { id: "bots", label: "Bot Settings", icon: Bot, path: "/bots" },
];

export function AppSidebar({
  activeSection,
  onSectionChange,
  isOpen,
  onClose,
}: AppSidebarProps) {
  const navigate = useNavigate();

  const handleNavigation = (item: typeof navItems[0]) => {
    navigate({ to: item.path });
    onSectionChange(item.id);
    onClose();
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed top-0 left-0 z-50 flex h-full w-64 flex-col border-r border-border bg-sidebar transition-transform duration-300 lg:static lg:translate-x-0",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary overflow-hidden">
              <img
                src="/bruh.chat.png"
                alt="App Logo"
                className="h-full w-full object-cover"
              />
            </div>
            <div>
              <h1 className="font-semibold text-sidebar-foreground">
                Bot Admin
              </h1>
              <p className="text-xs text-muted-foreground">Configuration</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground lg:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeSection === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleNavigation(item)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="border-t border-border p-4">
          <NavUser />
        </div>
      </aside>
    </>
  );
}
