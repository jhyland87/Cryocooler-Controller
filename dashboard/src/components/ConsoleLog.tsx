import { useRef, useEffect, useState, useCallback } from 'preact/hooks';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import Tooltip from '@mui/material/Tooltip';
import IconButton from '@mui/material/IconButton';
import { useConsoleLogs } from '../hooks/useConsoleLogs';
import type { LogEntry } from '../hooks/useConsoleLogs';

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Format a log entry's timestamp.
 * - epoch > 0  →  local wall-clock time  HH:MM:SS
 * - epoch == 0 →  device uptime          T+HH:MM:SS
 */
function formatTime(entry: LogEntry): string {
  if (entry.epoch > 0) {
    const d  = new Date(entry.epoch * 1000);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return `${hh}:${mm}:${ss}`;
  }
  // Fall back to millis-based uptime.
  const s  = Math.floor(entry.ms / 1000);
  const hh = String(Math.floor(s / 3600)).padStart(2, '0');
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return `T+${hh}:${mm}:${ss}`;
}

/**
 * Derive a terminal colour for a log line based on its content.
 * Order matters — more specific patterns should come first.
 */
function lineColor(text: string): string {
  const t = text.toLowerCase();
  if (t.includes('failed') || t.includes(' error') || t.includes('fault') || t.includes('halting')) {
    return '#f47067'; // red
  }
  if (t.includes('warn') || t.includes('timeout') || t.includes('retry')) {
    return '#e2b714'; // amber
  }
  if (
    t.includes('complete') || t.includes('success') ||
    t.includes('initialized') || t.includes('initialisation complete') ||
    t.includes('connected') || t.includes('started') ||
    t.includes('setup complete')
  ) {
    return '#57c7a9'; // green
  }
  return '#a9b1d6'; // default: muted lavender-white
}

// ─── Component ────────────────────────────────────────────────────────────────

export function ConsoleLog() {
  const { entries, clear } = useConsoleLogs();
  const scrollRef          = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Scroll to the bottom whenever new entries arrive, as long as auto-scroll
  // is engaged.  (The user can disengage it by scrolling up.)
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries, autoScroll]);

  // Re-engage auto-scroll if the user scrolls back within 40 px of the bottom.
  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
  }, []);

  const jumpToBottom = useCallback(() => {
    setAutoScroll(true);
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, []);

  return (
    <Box>

      {/* ── Header row ───────────────────────────────────────────────────── */}
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, gap: 1 }}>
        <Typography
          variant="subtitle2"
          sx={{
            flex: 1,
            color: 'text.secondary',
            fontWeight: 600,
            letterSpacing: 1,
            textTransform: 'uppercase',
            fontSize: '0.7rem',
          }}
        >
          Console Log
        </Typography>

        {/* Entry count badge */}
        <Chip
          label={entries.length}
          size="small"
          sx={{ height: 18, fontSize: '0.6rem', bgcolor: 'action.hover', color: 'text.secondary' }}
        />

        {/* "↓ Live" chip — only visible when scroll is locked away from bottom */}
        {!autoScroll && (
          <Tooltip title="Jump to latest and resume live scroll">
            <Chip
              label="↓ live"
              size="small"
              onClick={jumpToBottom}
              sx={{
                height: 18,
                fontSize: '0.6rem',
                cursor: 'pointer',
                bgcolor: 'rgba(79,195,247,0.12)',
                color: '#4fc3f7',
                border: '1px solid rgba(79,195,247,0.3)',
                '&:hover': { bgcolor: 'rgba(79,195,247,0.2)' },
              }}
            />
          </Tooltip>
        )}

        {/* Clear button */}
        <Tooltip title="Clear log">
          <IconButton
            size="small"
            onClick={clear}
            sx={{ p: 0.5, color: 'text.disabled', '&:hover': { color: 'text.secondary' } }}
          >
            {/* Using a Unicode × so we don't need an icon library import */}
            <Typography sx={{ fontSize: '0.75rem', lineHeight: 1, fontFamily: 'monospace' }}>✕</Typography>
          </IconButton>
        </Tooltip>
      </Box>

      {/* ── Terminal body ────────────────────────────────────────────────── */}
      <Box
        ref={scrollRef}
        onScroll={handleScroll}
        sx={{
          height: 240,
          overflowY: 'auto',
          bgcolor: '#0d1117',
          borderRadius: 1,
          p: '10px 14px',
          fontFamily: '"Fira Code", "Cascadia Code", "JetBrains Mono", "Consolas", monospace',
          fontSize: '0.72rem',
          lineHeight: 1.65,
          // Slim dark scrollbar to match terminal feel.
          '&::-webkit-scrollbar':       { width: 5 },
          '&::-webkit-scrollbar-thumb': { backgroundColor: '#30363d', borderRadius: 3 },
          '&::-webkit-scrollbar-track': { backgroundColor: 'transparent' },
        }}
      >
        {entries.length === 0 ? (
          <Typography sx={{ color: '#484f58', fontFamily: 'inherit', fontSize: 'inherit' }}>
            Waiting for log entries…
          </Typography>
        ) : (
          entries.map((entry, i) => (
            <Box
              key={`${entry.ms}-${i}`}
              sx={{ display: 'flex', gap: '10px', alignItems: 'baseline', minWidth: 0 }}
            >
              {/* Timestamp */}
              <Typography
                component="span"
                sx={{
                  color: '#484f58',
                  fontFamily: 'inherit',
                  fontSize: 'inherit',
                  flexShrink: 0,
                  userSelect: 'none',
                  minWidth: '7ch',
                }}
              >
                {formatTime(entry)}
              </Typography>

              {/* Message */}
              <Typography
                component="span"
                sx={{
                  color: lineColor(entry.text),
                  fontFamily: 'inherit',
                  fontSize: 'inherit',
                  wordBreak: 'break-word',
                  whiteSpace: 'pre-wrap',
                  minWidth: 0,
                }}
              >
                {entry.text.replace(/\n$/, '')}
              </Typography>
            </Box>
          ))
        )}
      </Box>
    </Box>
  );
}
