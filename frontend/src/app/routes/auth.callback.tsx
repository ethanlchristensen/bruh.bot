import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import { exchangeCodeForTokens, getDiscordUser } from '@/lib/auth';
import { useAuth } from '@/hooks/use-auth';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';

export const Route = createFileRoute('/auth/callback')({
  component: AuthCallback,
});

function AuthCallback() {
  const navigate = useNavigate();
  const { login } = useAuth();

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Get code from URL
        const params = new URLSearchParams(window.location.search);
        const code = params.get('code');
        const error = params.get('error');

        if (error) {
          toast.error(`Authentication failed: ${error}`);
          navigate({ to: '/login' });
          return;
        }

        if (!code) {
          toast.error('No authorization code received');
          navigate({ to: '/login' });
          return;
        }

        // Exchange code for tokens
        const tokens = await exchangeCodeForTokens(code);
        
        // Get user info
        const user = await getDiscordUser(tokens.access_token);

        // Update auth context
        login(tokens, user);

        toast.success(`Welcome back, ${user.global_name || user.username}!`);
        
        // Redirect to dashboard
        navigate({ to: '/general' });
      } catch (error) {
        console.error('Authentication error:', error);
        toast.error('Failed to authenticate. Please try again.');
        navigate({ to: '/login' });
      }
    };

    handleCallback();
  }, [navigate, login]);

  return (
    <div className="flex h-screen w-screen items-center justify-center">
      <div className="text-center space-y-4">
        <Spinner className="mx-auto" />
        <div>
          <h2 className="text-xl font-semibold">Authenticating...</h2>
          <p className="text-muted-foreground">Please wait while we sign you in</p>
        </div>
      </div>
    </div>
  );
}
