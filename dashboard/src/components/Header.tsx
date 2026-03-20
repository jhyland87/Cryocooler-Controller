import { useState, useEffect } from 'preact/hooks';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import type { ConnectionStatus } from '../hooks/useTelemetry';
import * as sx from '../theme/styles';

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
    <Typography variant="caption" sx={sx.headerClock}>
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
    <AppBar position="static" sx={sx.headerAppBar} elevation={0}>
      <Toolbar sx={sx.headerToolbar}>
        {/* Title */}
        <Typography variant="h6" sx={sx.headerTitle}>
          ❄ Cryocooler
        </Typography>

        {/* State name */}
        <Chip
          label={stateName || '—'}
          size="small"
          sx={sx.headerStateChip}
        />

        {/* Status text */}
        {statusText && (
          <Typography variant="caption" sx={sx.headerStatusText}>
            {statusText}
          </Typography>
        )}

        {/* Cooldown bar */}
        {cooldownPct !== undefined && cooldownPct > 0 && (
          <Box sx={sx.headerCooldownGroup}>
            <Typography variant="caption" sx={sx.headerCooldownLabel}>Cooldown</Typography>
            <Box sx={sx.headerCooldownTrack}>
              <Box sx={sx.headerCooldownBarFill(cooldownPct)} />
            </Box>
            <Typography variant="caption" sx={sx.headerCooldownPct}>{cooldownPct.toFixed(0)}%</Typography>
          </Box>
        )}

        <Box sx={sx.headerSpacer} />

        {/* On duration & time in state */}
        <Box sx={sx.headerDurationGroup}>
          {onDuration && (
            <Box sx={sx.headerDurationBlock}>
              <Typography variant="caption" sx={sx.headerDurationLabel}>On Duration</Typography>
              <Typography variant="caption" sx={sx.headerDurationValue}>{onDuration}</Typography>
            </Box>
          )}
          {timeInState && (
            <Box sx={sx.headerDurationBlock}>
              <Typography variant="caption" sx={sx.headerDurationLabel}>In State</Typography>
              <Typography variant="caption" sx={sx.headerDurationValue}>{timeInState}</Typography>
            </Box>
          )}
        </Box>

        {/* Frame counter */}
        <Typography variant="caption" sx={sx.headerFrameCounter}>
          #{frameCount}
        </Typography>

        {/* Connection status */}
        <Chip
          label={STATUS_LABELS[connectionStatus]}
          size="small"
          color={STATUS_COLORS[connectionStatus]}
          variant="outlined"
          sx={sx.headerConnectionChip}
        />

        <LiveClock />
      </Toolbar>
    </AppBar>
  );
}
