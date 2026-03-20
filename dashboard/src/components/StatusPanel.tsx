import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import type { TelemetryData } from '../types/telemetry';
import * as sx from '../theme/styles';

// ─── Individual LED indicator ─────────────────────────────────────────────────

interface LedProps {
  label:   string;
  active:  boolean;
  color:   string;
  tooltip?: string;
}

function Led({ label, active, color, tooltip }: LedProps) {
  const dot = (
    <Box sx={sx.ledContainer}>
      <Box sx={sx.ledDot(active, color)} />
      <Typography variant="caption" sx={sx.ledLabel(active, color)}>
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
  const fault       = Boolean(data.indicator?.fault);
  const ready       = Boolean(data.indicator?.ready);
  const alarmRelay  = Boolean(data.relay?.alarm);
  const normalRelay = Boolean(data.relay?.normal);
  const compressor  = Boolean(data.compressor?.status);
  const motion      = Boolean(data.imu?.motion);

  const faults10m = data.faults?.count_10m ?? 0;
  const faults30m = data.faults?.count_30m ?? 0;
  const faults60m = data.faults?.count_60m ?? 0;

  return (
    <Box>
      {/* LED row */}
      <Box sx={sx.ledRow}>
        <Led label="READY"  active={ready}       color="#66bb6a" tooltip="System is ready / running" />
        <Led label="FAULT"  active={fault}       color="#ef5350" tooltip="Active fault condition" />
        <Led label="ALARM"  active={alarmRelay}  color="#ffa726" tooltip="Alarm relay energised" />
        <Led label="NORMAL" active={normalRelay} color="#29b6f6" tooltip="Relay in normal (non-bypass) position" />
        <Led label="COMP"   active={compressor}  color="#ce93d8" tooltip="Compressor active" />
        <Led label="MOTION" active={motion}      color="#ffca28" tooltip="IMU overstroke / motion detected" />
      </Box>

      {/* Fault counters */}
      <Box sx={sx.faultCounterRow}>
        {[
          { label: 'Faults / 10 m', value: faults10m },
          { label: 'Faults / 30 m', value: faults30m },
          { label: 'Faults / 60 m', value: faults60m },
        ].map(({ label, value }) => {
          const hasValue = Number(value) > 0;
          return (
            <Box key={label} sx={sx.faultCounterBox(hasValue)}>
              <Typography variant="h6" sx={sx.faultCounterValue(hasValue)}>
                {value}
              </Typography>
              <Typography variant="caption" sx={sx.faultCounterLabel(hasValue)}>
                {label}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
