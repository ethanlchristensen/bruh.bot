import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import {
  AlertCircle,
  Clock,
  Filter,
  Music as MusicIcon,
  Pause,
  Play,
  Plus,
  Search,
  SkipForward,
  Trash2,
  User,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { useMusic } from '@/contexts/music-context';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { GuildSelector } from '@/components/guild-selector';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export const Route = createFileRoute('/_main/music')({
  component: MusicComponent,
});

function formatTime(seconds: number) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

const FILTER_PRESETS = [
  { value: 'none', label: 'None' },
  { value: 'bassboost', label: 'Bass Boost' },
  { value: 'nightcore', label: 'Nightcore' },
  { value: 'vaporwave', label: 'Vaporwave' },
  { value: 'treble', label: 'Treble Boost' },
  { value: 'echo', label: 'Echo' },
  { value: 'vibrato', label: 'Vibrato' },
  { value: 'tremolo', label: 'Tremolo' },
  { value: 'distortion', label: 'Distortion' },
  { value: 'mono', label: 'Mono' },
  { value: 'volume_boost', label: 'Volume Boost' },
  { value: 'lofi', label: 'Lo-Fi' },
  { value: 'chorus', label: 'Chorus' },
  { value: 'reverse', label: 'Reverse' },
  { value: 'phaser', label: 'Phaser' },
  { value: 'chipmunk', label: 'Chipmunk' },
  { value: 'slowmo', label: 'Slow Motion' },
  { value: 'robot', label: 'Robot Voice' },
  { value: 'underwater', label: 'Underwater' },
  { value: 'telephone', label: 'Telephone' },
  { value: 'crystalize', label: 'Crystalize' },
  { value: 'compressor', label: 'Compressor' },
  { value: 'earwax', label: 'Earwax' },
  { value: 'reverb', label: 'Shimmering Reverb' },
  { value: 'stereowide', label: 'Stereo Wide' },
  { value: 'pitch_up', label: 'Pitch Up' },
  { value: 'pitch_down', label: 'Pitch Down' },
  { value: '8bit', label: '8-Bit' },
];

function MusicComponent() {
  const {
    state,
    isConnected,
    error,
    lastMessage,
    skip,
    pause,
    resume,
    seek,
    add,
    remove,
    connect,
    disconnect,
  } = useMusic();

  const [query, setQuery] = useState('');
  const [filterPreset, setFilterPreset] = useState('none');
  const [localPos, setLocalPos] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  // Sync local position with state position
  useEffect(() => {
    if (!isDragging && state) {
      setLocalPos(state.position);
    }
  }, [state, isDragging]);

  // Interpolate position if playing
  useEffect(() => {
    if (!state || state.is_paused || !state.is_playing || isDragging) return;

    const interval = setInterval(() => {
      setLocalPos((prev) => {
        const duration = state.current_song?.duration || 0;
        if (duration > 0 && prev >= duration) return prev;
        return prev + 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [state, isDragging]);

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      add(query.trim(), filterPreset);
      setQuery('');
      setFilterPreset('none'); // Reset filter after adding
    }
  };

  const currentSong = state?.current_song;
  const duration = currentSong?.duration || 0;

  return (
    <div className="space-y-6 max-w-5xl mx-auto w-full pb-10">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <GuildSelector />

          {isConnected ? (
            <Button
              variant="outline"
              size="sm"
              onClick={disconnect}
              className="gap-2"
            >
              <WifiOff className="h-4 w-4" /> Disconnect
            </Button>
          ) : (
            <Button size="sm" onClick={connect} className="gap-2">
              <Wifi className="h-4 w-4" /> Connect to Guild
            </Button>
          )}

          <Badge
            variant={isConnected ? 'outline' : 'destructive'}
            className="gap-1"
          >
            {isConnected ? (
              <Wifi className="h-3 w-3" />
            ) : (
              <WifiOff className="h-3 w-3" />
            )}
            {isConnected ? 'Connected' : 'Disconnected'}
          </Badge>
        </div>
        {lastMessage && (
          <div className="text-sm text-muted-foreground animate-in fade-in slide-in-from-top-1">
            {lastMessage}
          </div>
        )}
      </div>

      {(error || (state as any)?.error) && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardContent className="pt-6 flex items-center gap-3 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <p>{error || (state as any)?.error}</p>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-col gap-6">
        {/* Now Playing Section */}
        <Card className="w-full">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MusicIcon className="h-5 w-5" />
              Now Playing
            </CardTitle>
            <CardDescription>
              {!isConnected
                ? 'Connect to a guild to view status'
                : state?.is_playing
                  ? state.is_paused
                    ? 'Paused'
                    : 'Currently playing'
                  : 'Nothing playing'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {currentSong ? (
              <div className="flex flex-col md:flex-row gap-6 w-full">
                {currentSong.thumbnail_url && (
                  <div className="aspect-video w-full md:w-64 lg:w-80 shrink-0 overflow-hidden rounded-md border bg-muted/30 relative">
                    <img
                      src={currentSong.thumbnail_url}
                      alt={currentSong.title}
                      className="w-full h-full object-cover"
                    />
                    {currentSong.filter_preset &&
                      currentSong.filter_preset !== 'none' && (
                        <div className="absolute top-2 right-2">
                          <Badge
                            variant="secondary"
                            className="bg-black/50 backdrop-blur-md text-white border-none shadow-sm gap-1 hover:bg-black/60"
                          >
                            <Filter className="h-3 w-3" />
                            {FILTER_PRESETS.find(
                              (p) => p.value === currentSong.filter_preset,
                            )?.label || currentSong.filter_preset}
                          </Badge>
                        </div>
                      )}
                  </div>
                )}

                <div className="flex-1 flex flex-col justify-between gap-6">
                  <div className="space-y-2">
                    <h3 className="font-bold text-xl line-clamp-2">
                      {currentSong.webpage_url ? (
                        <a
                          href={currentSong.webpage_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:text-primary transition-colors underline-offset-4 hover:underline"
                        >
                          {currentSong.title}
                        </a>
                      ) : (
                        currentSong.title
                      )}
                    </h3>
                    <p className="text-muted-foreground flex items-center gap-1">
                      <User className="h-4 w-4" />
                      {currentSong.author_url ? (
                        <a
                          href={currentSong.author_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:text-primary transition-colors"
                        >
                          {currentSong.author}
                        </a>
                      ) : (
                        currentSong.author
                      )}
                    </p>
                    <Badge variant="secondary" className="mt-2">
                      Requested by: {currentSong.requested_by}
                    </Badge>
                  </div>

                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Slider
                        value={[localPos]}
                        max={duration}
                        step={1}
                        onValueChange={(vals) => {
                          setIsDragging(true);
                          setLocalPos(vals[0]);
                        }}
                        onValueCommit={(vals) => {
                          setIsDragging(false);
                          seek(vals[0]);
                        }}
                        disabled={!isConnected}
                      />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{formatTime(localPos)}</span>
                        <span>{formatTime(duration)}</span>
                      </div>
                    </div>

                    <div className="flex justify-start gap-4">
                      {state.is_paused ? (
                        <Button
                          size="icon"
                          variant="outline"
                          onClick={resume}
                          disabled={!isConnected}
                        >
                          <Play className="h-5 w-5 fill-current" />
                        </Button>
                      ) : (
                        <Button
                          size="icon"
                          variant="outline"
                          onClick={pause}
                          disabled={!isConnected || !state.is_playing}
                        >
                          <Pause className="h-5 w-5 fill-current" />
                        </Button>
                      )}
                      <Button
                        size="icon"
                        variant="outline"
                        onClick={skip}
                        disabled={!isConnected || !state.is_playing}
                      >
                        <SkipForward className="h-5 w-5 fill-current" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-40 flex flex-col items-center justify-center text-muted-foreground bg-muted/30 rounded-lg border border-dashed">
                <MusicIcon className="h-10 w-10 mb-2 opacity-20" />
                <p>{isConnected ? 'No track is active' : 'Disconnected'}</p>
              </div>
            )}

            <Separator />

            <form onSubmit={handleAdd} className="space-y-3">
              <label className="text-sm font-medium">Add to Queue</label>

              <div className="flex flex-col gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search or URL..."
                    className="pl-9"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    disabled={!isConnected}
                  />
                </div>

                <div className="flex gap-2">
                  <Select
                    value={filterPreset}
                    onValueChange={setFilterPreset}
                    disabled={!isConnected}
                  >
                    <SelectTrigger className="flex-1">
                      <SelectValue placeholder="Audio Filter" />
                    </SelectTrigger>
                    <SelectContent>
                      {FILTER_PRESETS.map((preset) => (
                        <SelectItem key={preset.value} value={preset.value}>
                          {preset.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <Button
                    type="submit"
                    size="icon"
                    disabled={!isConnected || !query.trim()}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Queue Section */}
        <Card className="w-full">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Queue
            </CardTitle>
            <CardDescription>
              {state?.queue.length || 0} tracks in queue
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {state?.queue.length ? (
                state.queue.map((item, i) => (
                  <div
                    key={`${item.title}-${i}`}
                    className="flex items-center justify-between p-3 rounded-md hover:bg-accent group transition-colors"
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      {item.thumbnail_url ? (
                        <div className="h-10 w-16 flex-shrink-0 overflow-hidden rounded bg-muted/30 relative">
                          <img
                            src={item.thumbnail_url}
                            alt=""
                            className="h-full w-full object-cover"
                          />
                          {item.filter_preset &&
                            item.filter_preset !== 'none' && (
                              <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                                <Filter className="h-3 w-3 text-white" />
                              </div>
                            )}
                        </div>
                      ) : (
                        <span className="text-sm text-muted-foreground w-4 text-center">
                          {i + 1}
                        </span>
                      )}
                      <div className="overflow-hidden ml-2">
                        <div className="flex items-center gap-2">
                          <p className="font-medium truncate text-sm">
                            {item.webpage_url ? (
                              <a
                                href={item.webpage_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="hover:text-primary transition-colors underline-offset-4 hover:underline"
                              >
                                {item.title}
                              </a>
                            ) : (
                              item.title
                            )}
                          </p>
                          {item.filter_preset &&
                            item.filter_preset !== 'none' && (
                              <Badge
                                variant="outline"
                                className="text-[10px] h-4 px-1 py-0 border-primary/20 bg-primary/5"
                              >
                                <Filter className="h-2 w-2 mr-1" />
                                {FILTER_PRESETS.find(
                                  (p) => p.value === item.filter_preset,
                                )?.label || item.filter_preset}
                              </Badge>
                            )}
                        </div>
                        <p className="text-xs text-muted-foreground truncate">
                          {item.author_url ? (
                            <a
                              href={item.author_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="hover:text-primary transition-colors"
                            >
                              {item.author}
                            </a>
                          ) : (
                            item.author
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 flex-shrink-0">
                      <span className="text-xs text-muted-foreground">
                        {formatTime(item.duration)}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => remove(i)}
                        disabled={!isConnected}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="py-20 text-center text-muted-foreground">
                  <p>
                    {isConnected
                      ? 'Queue is empty'
                      : 'Connect to a guild to view queue'}
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
