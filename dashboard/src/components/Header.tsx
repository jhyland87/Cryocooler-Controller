import { useState, useEffect } from 'preact/hooks';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import type { ConnectionStatus } from '../hooks/useTelemetry';

// ─── Connection badge ─────────────────────────────────────────────────────────

const STATUS_LABELS: Record<ConnectionStatus, string> = {
  connecting:   'Connecting…',
  connected:    'WebSocket',
  disconnected: 'Disconnected',
};

const STATUS_COLORS: Record<ConnectionStatus, 'success' | 'warning' | 'error' | 'default'> = {
  connecting:   'default',
  connected:    'success',
  disconnected: 'error',
};

// ─── Live clock ───────────────────────────────────────────────────────────────

function LiveClock() {
  const [time, setTime] = useState(() => new Date().toLocaleTimeString());

  useEffect(() => {
    const id = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', fontFamily: 'monospace', fontSize: '0.85rem' }}>
      {time}
    </Typography>
  );
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface Props {
  connectionStatus:  ConnectionStatus;
  stateName:         string;
  statusText:        string;
  onDuration:        string;
  timeInState:       string;
  cooldownPct:       number | undefined;
  frameCount:        number;
}

export function Header({
  connectionStatus,
  stateName,
  statusText,
  onDuration,
  timeInState,
  cooldownPct,
  frameCount,
}: Props) {
  return (
    <AppBar position="static" sx={{ bgcolor: '#0d1117', borderBottom: '1px solid rgba(255,255,255,0.08)' }} elevation={0}>
      <Toolbar sx={{ gap: 2, flexWrap: 'wrap', minHeight: { xs: 56 } }}>
        {/* Title */}
        <Typography
          variant="h6"
          sx={{ fontWeight: 700, letterSpacing: 1, fontSize: '1rem', color: '#90caf9', flexShrink: 0 }}
        >
          ❄ Cryocooler
        </Typography>

        {/* State name */}
        <Chip
          label={stateName || '—'}
          size="small"
          sx={{ bgcolor: '#1565c0', color: '#fff', fontWeight: 700, fontSize: '0.72rem', letterSpacing: 0.5 }}
        />

        {/* Status text */}
        {statusText && (
          <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)', flexShrink: 0, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {statusText}
          </Typography>
        )}

        {/* Cooldown bar */}
        {cooldownPct !== undefined && cooldownPct > 0 && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexShrink: 0 }}>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.65rem' }}>Cooldown</Typography>
            <Box sx={{ width: 80, height: 6, bgcolor: 'rgba(255,255,255,0.1)', borderRadius: 3, overflow: 'hidden' }}>
              <Box sx={{ width: `${cooldownPct}%`, height: '100%', bgcolor: '#29b6f6', borderRadius: 3, transition: 'width 0.5s ease' }} />
            </Box>
            <Typography variant="caption" sx={{ color: '#29b6f6', fontSize: '0.65rem', fontWeight: 700 }}>{cooldownPct.toFixed(0)}%</Typography>
          </Box>
        )}

        <Box sx={{ flex: 1 }} />

        {/* On duration & time in state */}
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          {onDuration && (
            <Box sx={{ textAlign: 'right' }}>
              <Typography variant="caption" sx={{ display: 'block', color: 'rgba(255,255,255,0.35)', fontSize: '0.6rem', lineHeight: 1 }}>On Duration</Typography>
              <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'rgba(255,255,255,0.7)', fontSize: '0.78rem' }}>{onDuration}</Typography>
            </Box>
          )}
          {timeInState && (
            <Box sx={{ textAlign: 'right' }}>
              <Typography variant="caption" sx={{ display: 'block', color: 'rgba(255,255,255,0.35)', fontSize: '0.6rem', lineHeight: 1 }}>In State</Typography>
              <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'rgba(255,255,255,0.7)', fontSize: '0.78rem' }}>{timeInState}</Typography>
            </Box>
          )}
        </Box>

        {/* Frame counter */}
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.25)', fontSize: '0.6rem', fontFamily: 'monospace' }}>
          #{frameCount}
        </Typography>

        {/* Connection status */}
        <Chip
          label={STATUS_LABELS[connectionStatus]}
          size="small"
          color={STATUS_COLORS[connectionStatus]}
          variant="outlined"
          sx={{ fontSize: '0.65rem', height: 20, flexShrink: 0 }}
        />

        <LiveClock />
      </Toolbar>
    </AppBar>
  );
}
