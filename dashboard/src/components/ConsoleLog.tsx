import { useRef, useEffect, useState, useCallback } from 'preact/hooks';
import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import Tooltip from '@mui/material/Tooltip';
import IconButton from '@mui/material/IconButton';
import { useConsoleLogs } from '../hooks/useConsoleLogs';
import type { LogEntry } from '../types/hooks';
import type { ConsoleLogProps } from '../types/components';
import * as sx from '../theme/styles';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTime(entry: LogEntry): string {
  if (entry.epoch > 0) {
    const d  = new Date(entry.epoch * 1000);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return `${hh}:${mm}:${ss}`;
  }
  const s  = Math.floor(entry.ms / 1000);
  const hh = String(Math.floor(s / 3600)).padStart(2, '0');
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return `T+${hh}:${mm}:${ss}`;
}

function lineColor(text: string): string {
  const t = text.toLowerCase();
  if (t.includes('failed') || t.includes(' error') || t.includes('fault') || t.includes('halting')) {
    return '#f47067';
  }
  if (t.includes('warn') || t.includes('timeout') || t.includes('retry')) {
    return '#e2b714';
  }
  if (
    t.includes('complete') || t.includes('success') ||
    t.includes('initialized') || t.includes('initialisation complete') ||
    t.includes('connected') || t.includes('started') ||
    t.includes('setup complete')
  ) {
    return '#57c7a9';
  }
  return '#a9b1d6';
}

// ─── Component ────────────────────────────────────────────────────────────────

export function ConsoleLog({ logEpoch, loading }: ConsoleLogProps) {
  const { entries, clear } = useConsoleLogs(logEpoch);
  const scrollRef          = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries, autoScroll]);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
  }, []);

  const jumpToBottom = useCallback(() => {
    setAutoScroll(true);
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, []);

  if (loading) {
    return (
      <Box>
        <Box sx={sx.consoleHeaderRow}>
          <Skeleton variant="text" width={120} height={16} sx={sx.skeletonConsoleFlex} />
          <Skeleton variant="rounded" width={30} height={18} />
        </Box>
        <Box sx={sx.consoleTerminal}>
          {Array.from({ length: 8 }).map((_, i) => (
            <Box key={i} sx={sx.consoleEntryRow}>
              <Skeleton variant="text" width={60} height={14} sx={sx.skeletonConsoleDarkTimestamp} />
              <Skeleton variant="text" height={14} sx={sx.skeletonConsoleDarkLine} />
            </Box>
          ))}
        </Box>
      </Box>
    );
  }

  return (
    <Box>

      {/* ── Header row ───────────────────────────────────────────────────── */}
      <Box sx={sx.consoleHeaderRow}>
        <Typography variant="subtitle2" sx={sx.consoleTitle}>
          Console Log (tail)
        </Typography>

        {/* Entry count badge */}
        <Chip label={entries.length} size="small" sx={sx.consoleBadge} />

        {/* "↓ Live" chip */}
        {!autoScroll && (
          <Tooltip title="Jump to latest and resume live scroll">
            <Chip label="↓ live" size="small" onClick={jumpToBottom} sx={sx.consoleLiveChip} />
          </Tooltip>
        )}

        {/* Clear button */}
        <Tooltip title="Clear log">
          <IconButton size="small" onClick={clear} sx={sx.consoleClearBtn}>
            <Typography sx={sx.consoleClearIcon}>✕</Typography>
          </IconButton>
        </Tooltip>
      </Box>

      {/* ── Terminal body ────────────────────────────────────────────────── */}
      <Box ref={scrollRef} onScroll={handleScroll} sx={sx.consoleTerminal}>
        {entries.length === 0 ? (
          <Typography sx={sx.consoleEmpty}>
            Waiting for log entries…
          </Typography>
        ) : (
          entries.map((entry, i) => (
            <Box
              key={`${entry.ms}-${i}`}
              sx={sx.consoleEntryRow}
            >
              <Typography component="span" sx={sx.consoleTimestamp}>
                {formatTime(entry)}
              </Typography>
              <Typography component="span" sx={sx.consoleMessage(lineColor(entry.text))}>
                {entry.text.replace(/\n$/, '')}
              </Typography>
            </Box>
          ))
        )}
      </Box>
    </Box>
  );
}
