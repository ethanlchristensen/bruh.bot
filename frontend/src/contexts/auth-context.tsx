import * as React from 'react';
import type { AuthState, AuthTokens, DiscordUser } from '@/lib/auth';
import {
  clearAuthState,
  getDiscordUser,
  loadAuthState,
  refreshAccessToken,
  revokeToken,
  saveAuthState,
} from '@/lib/auth';

interface AuthContextType extends AuthState {
  login: (tokens: AuthTokens, user: DiscordUser) => void;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [state, setState] = React.useState<AuthState>({
    user: null,
    tokens: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // Load auth state from localStorage on mount
  React.useEffect(() => {
    const initAuth = async () => {
      const stored = loadAuthState();
      if (!stored) {
        setState((prev) => ({ ...prev, isLoading: false }));
        return;
      }

      // Check if token is expired and refresh if needed
      const now = Date.now();
      const tokenExpiry = stored.tokens.expires_in * 1000;

      try {
        let tokens = stored.tokens;

        // If token is about to expire (within 5 minutes), refresh it
        if (tokenExpiry - now < 5 * 60 * 1000) {
          tokens = await refreshAccessToken(stored.tokens.refresh_token);
          saveAuthState({ user: stored.user, tokens });
        }

        setState({
          user: stored.user,
          tokens,
          isAuthenticated: true,
          isLoading: false,
        });
      } catch (error) {
        console.error('Failed to refresh token:', error);
        clearAuthState();
        setState({
          user: null,
          tokens: null,
          isAuthenticated: false,
          isLoading: false,
        });
      }
    };

    initAuth();
  }, []);

  const login = React.useCallback((tokens: AuthTokens, user: DiscordUser) => {
    saveAuthState({ user, tokens });
    setState({
      user,
      tokens,
      isAuthenticated: true,
      isLoading: false,
    });
  }, []);

  const logout = React.useCallback(async () => {
    if (state.tokens) {
      try {
        await revokeToken(state.tokens.access_token);
      } catch (error) {
        console.error('Failed to revoke token:', error);
      }
    }

    clearAuthState();
    setState({
      user: null,
      tokens: null,
      isAuthenticated: false,
      isLoading: false,
    });
  }, [state.tokens]);

  const refreshUser = React.useCallback(async () => {
    if (!state.tokens) return;

    try {
      const user = await getDiscordUser(state.tokens.access_token);
      saveAuthState({ user, tokens: state.tokens });
      setState((prev) => ({ ...prev, user }));
    } catch (error) {
      console.error('Failed to refresh user:', error);
      // If refresh fails, try to refresh token
      if (state.tokens.refresh_token) {
        try {
          const tokens = await refreshAccessToken(state.tokens.refresh_token);
          const user = await getDiscordUser(tokens.access_token);
          saveAuthState({ user, tokens });
          setState((prev) => ({ ...prev, user, tokens }));
        } catch (refreshError) {
          console.error('Failed to refresh token:', refreshError);
          await logout();
        }
      }
    }
  }, [state.tokens, logout]);

  const value = React.useMemo(
    () => ({
      ...state,
      login,
      logout,
      refreshUser,
    }),
    [state, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
