import { createFileRoute, Navigate } from '@tanstack/react-router';

export const Route = createFileRoute('/_main/config/')({
  component: ConfigIndexRedirect,
});

function ConfigIndexRedirect() {
  return <Navigate to="/config/ai" />;
}