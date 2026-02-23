import { createFileRoute } from '@tanstack/react-router';
import { ThemeSettings } from '@/components/theme/theme-settings';

export const Route = createFileRoute('/_main/profile')({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <div className="overflow-y-scroll h-full w-full">
      <div className="container mx-auto max-w-4xl py-8 px-4">
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight">
            Profile Settings
          </h1>
          <p className="text-muted-foreground mt-2">
            Manage your profile information and preferences
          </p>
        </div>

        <ThemeSettings />
      </div>
    </div>
  );
}
