import { Outlet, createFileRoute } from '@tanstack/react-router';
import { ContentLayout } from '@/components/layouts/content-layout';
import { AppSidebar } from '@/components/sidebar/app-sidebar';

export const Route = createFileRoute('/_main')({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <div className="flex w-full">
      <AppSidebar />
      <ContentLayout>
        <Outlet />
      </ContentLayout>
    </div>
  );
}
