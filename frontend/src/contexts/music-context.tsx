import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useGuild } from './guild-context';
import type { ReactNode } from 'react';
import { env } from '@/config/env';
import { useAuth } from '@/hooks/use-auth';

export interface Song {
  title: string;
  author: string;
  author_url?: string;
  duration: number;
  requested_by: string;
  url?: string;
  webpage_url?: string;
  thumbnail_url?: string;
  index?: number;
  filter_preset?: string | null;
}

export interface MusicState {
  guild_id: string;
  is_playing: boolean;
  is_paused: boolean;
  current_song: Song | null;
  queue: Array<Song>;
  position: number;
  error?: string;
}

interface MusicContextType {
  state: MusicState | null;
  isConnected: boolean;
  error: string | null;
  lastMessage: string | null;
  sendMessage: (type: string, data?: any) => void;
  skip: () => void;
  pause: () => void;
  resume: () => void;
  seek: (seconds: number) => void;
  add: (query: string, filterPreset?: string) => void;
  remove: (index: number) => void;
  filter: (filterPreset: string) => void;
  connect: () => void;
  disconnect: () => void;
}

const MusicContext = createContext<MusicContextType | undefined>(undefined);

export function MusicProvider({ children }: { children: ReactNode }) {
  const { selectedGuildId } = useGuild();
  const { user } = useAuth();
  const [state, setState] = useState<MusicState | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isClosingRef = useRef(false);

  const disconnect = useCallback(() => {
    // Clear any existing timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (socketRef.current) {
      console.log('MusicProvider: Disconnecting intentionally');
      isClosingRef.current = true;
      socketRef.current.onclose = null;
      socketRef.current.onerror = null;
      socketRef.current.onmessage = null;
      socketRef.current.onopen = null;
      socketRef.current.close();
      socketRef.current = null;
    }

    setIsConnected(false);
    setState(null);
    setError(null);
  }, []);

  const connect = useCallback(() => {
    if (!selectedGuildId) {
      console.log('MusicProvider: connect skipped - no selectedGuildId');
      return;
    }

    disconnect(); // Ensure any old connection is cleaned up

    isClosingRef.current = false;
    const wsUrl = `${env.MUSIC_WS_URL}/${selectedGuildId}`;
    console.log('MusicProvider: Connecting to', wsUrl);
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('Music WebSocket connected');
      setIsConnected(true);
      setError(null);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'initial_state' || data.type === 'state_update') {
          setState(data.data);
        } else if (data.type === 'error') {
          setError(data.message);
          setLastMessage(`Error: ${data.message}`);
        }
      } catch (err) {
        console.error('Error parsing music websocket message:', err);
      }
    };

    socket.onclose = (event) => {
      if (isClosingRef.current) {
        console.log('Music WebSocket closed intentionally (isClosingRef=true)');
        return;
      }

      console.log('Music WebSocket disconnected', event.code, event.reason);
      setIsConnected(false);

      // Attempt to reconnect after 3 seconds
      if (!reconnectTimeoutRef.current) {
        console.log('MusicProvider: Scheduling reconnection in 3s');
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null;
          connect();
        }, 3000);
      }
    };

    socket.onerror = (err) => {
      console.error('Music WebSocket error:', err);
      setError('Connection error');
    };

    socketRef.current = socket;
  }, [selectedGuildId, disconnect]);

  useEffect(() => {
    // Disconnect when guild changes, user must manually reconnect
    console.log(
      'MusicProvider: selectedGuildId changed, disconnecting old socket if any',
    );
    disconnect();
  }, [selectedGuildId, disconnect]);

  useEffect(() => {
    return () => {
      console.log('MusicProvider: useEffect cleanup - closing socket');
      disconnect();
    };
  }, [disconnect]);

  const sendMessage = useCallback((type: string, data?: any) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type, data }));
    }
  }, []);

  const skip = useCallback(() => sendMessage('skip'), [sendMessage]);
  const pause = useCallback(() => sendMessage('pause'), [sendMessage]);
  const resume = useCallback(() => sendMessage('resume'), [sendMessage]);
  const seek = useCallback(
    (seconds: number) => sendMessage('seek', { seconds }),
    [sendMessage],
  );
  const add = useCallback(
    (query: string, filterPreset: string = 'none') => {
      sendMessage('add', {
        query,
        requested_by: user?.username || 'Web Dashboard',
        filter_preset: filterPreset,
      });
      setLastMessage(
        `Adding: ${query} ${filterPreset !== 'none' ? `(${filterPreset})` : ''}`,
      );
    },
    [sendMessage, user],
  );
  const remove = useCallback(
    (index: number) => {
      sendMessage('remove', { index });
      setLastMessage(`Removed index ${index}`);
    },
    [sendMessage],
  );
  const filter = useCallback(
    (filterPreset: string) => {
      sendMessage('filter', { filter_preset: filterPreset });
      setLastMessage(`Filter changed to ${filterPreset}`);
    },
    [sendMessage],
  );

  return (
    <MusicContext.Provider
      value={{
        state,
        isConnected,
        error,
        lastMessage,
        sendMessage,
        skip,
        pause,
        resume,
        seek,
        add,
        remove,
        filter,
        connect,
        disconnect,
      }}
    >
      {children}
    </MusicContext.Provider>
  );
}

export function useMusic() {
  const context = useContext(MusicContext);
  if (context === undefined) {
    throw new Error('useMusic must be used within a MusicProvider');
  }
  return context;
}
