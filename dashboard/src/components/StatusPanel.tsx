import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import type { TelemetryData } from '../types/telemetry';

// ─── Individual LED indicator ─────────────────────────────────────────────────

interface LedProps {
  label:   string;
  active:  boolean;
  color:   string;   // MUI palette colour, e.g. 'error.main'
  tooltip?: string;
}

function Led({ label, active, color, tooltip }: LedProps) {
  const dot = (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5 }}>
      <Box
        sx={{
          width: 18,
          height: 18,
          borderRadius: '50%',
          bgcolor: active ? color : 'action.disabled',
          boxShadow: active ? `0 0 8px 2px ${color}` : 'none',
          transition: 'all 0.3s ease',
          border: '2px solid',
          borderColor: active ? color : 'divider',
        }}
      />
      <Typography
        variant="caption"
        sx={{
          fontSize: '0.6rem',
          fontWeight: active ? 700 : 400,
          color: active ? color : 'text.disabled',
          textTransform: 'uppercase',
          letterSpacing: 0.5,
          lineHeight: 1,
        }}
      >
        {label}
      </Typography>
    </Box>
  );

  return tooltip ? <Tooltip title={tooltip} arrow>{dot}</Tooltip> : dot;
}

// ─── Status panel ─────────────────────────────────────────────────────────────

interface Props {
  data: TelemetryData;
}

export function StatusPanel({ data }: Props) {
  const fault      = Boolean(data['indicator.fault']);
  const ready      = Boolean(data['indicator.ready']);
  const alarmRelay = Boolean(data['relay.alarm']);
  const normalRelay = Boolean(data['relay.normal']);
  const compressor = Boolean(data['compressor.status']);
  const motion     = Boolean(data['imu.motion']);

  const faults10m  = data['faults.count_10m'] ?? 0;
  const faults30m  = data['faults.count_30m'] ?? 0;
  const faults60m  = data['faults.count_60m'] ?? 0;

  return (
    <Box sx={{ bgcolor: 'background.paper', borderRadius: 1, p: 2, border: '1px solid', borderColor: 'divider' }}>
      <Typography variant="subtitle2" sx={{ mb: 1.5, color: 'text.secondary', fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase', fontSize: '0.7rem' }}>
        Status &amp; Indicators
      </Typography>

      {/* LED row */}
      <Box sx={{ display: 'flex', gap: 2.5, flexWrap: 'wrap', mb: 2 }}>
        <Led
          label="READY"
          active={ready}
          color="#66bb6a"
          tooltip="System is ready / running"
        />
        <Led
          label="FAULT"
          active={fault}
          color="#ef5350"
          tooltip="Active fault condition"
        />
        <Led
          label="ALARM"
          active={alarmRelay}
          color="#ffa726"
          tooltip="Alarm relay energised"
        />
        <Led
          label="NORMAL"
          active={normalRelay}
          color="#29b6f6"
          tooltip="Relay in normal (non-bypass) position"
        />
        <Led
          label="COMP"
          active={compressor}
          color="#ce93d8"
          tooltip="Compressor active"
        />
        <Led
          label="MOTION"
          active={motion}
          color="#ffca28"
          tooltip="IMU overstroke / motion detected"
        />
      </Box>

      {/* Fault counters */}
      <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
        {[
          { label: 'Faults / 10 m', value: faults10m },
          { label: 'Faults / 30 m', value: faults30m },
          { label: 'Faults / 60 m', value: faults60m },
        ].map(({ label, value }) => (
          <Box
            key={label}
            sx={{
              flex: '1 1 80px',
              textAlign: 'center',
              bgcolor: Number(value) > 0 ? 'error.dark' : 'action.selected',
              borderRadius: 1,
              py: 0.75,
              px: 1,
              transition: 'background-color 0.3s',
            }}
          >
            <Typography variant="h6" sx={{ lineHeight: 1, fontWeight: 700, color: Number(value) > 0 ? '#fff' : 'text.secondary' }}>
              {value}
            </Typography>
            <Typography variant="caption" sx={{ fontSize: '0.6rem', color: Number(value) > 0 ? 'rgba(255,255,255,0.7)' : 'text.disabled', letterSpacing: 0.5 }}>
              {label}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
