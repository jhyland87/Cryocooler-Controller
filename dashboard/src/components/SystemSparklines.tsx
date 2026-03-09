import { SparkLineChart } from '@mui/x-charts/SparkLineChart';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import LinearProgress from '@mui/material/LinearProgress';
import type { DataPoint } from '../types/telemetry';

interface GaugeSparkProps {
  label:      string;
  data:       DataPoint[];
  color:      string;
  unit:       string;
  warnAbove?: number;
  max?:       number;
}

function GaugeSpark({ label, data, color, unit, warnAbove, max = 100 }: GaugeSparkProps) {
  const values = data.map((p) => p.v);
  const last   = values.length > 0 ? values[values.length - 1] : null;
  const pct    = last !== null ? Math.min(100, (last / max) * 100) : 0;
  const warn   = warnAbove !== undefined && last !== null && last > warnAbove;

  return (
    <Box sx={{
      flex: '1 1 140px',
      minWidth: 120,
      bgcolor: 'background.paper',
      borderRadius: 1,
      p: 1.5,
      border: '1px solid',
      borderColor: warn ? 'warning.dark' : 'divider',
    }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.8, fontSize: '0.65rem' }}>
          {label}
        </Typography>
        {last !== null && (
          <Typography variant="caption" sx={{ color: warn ? 'warning.light' : color, fontWeight: 700, fontSize: '0.75rem' }}>
            {last.toFixed(1)}{unit}
          </Typography>
        )}
      </Box>
      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{
          mb: 0.75,
          height: 4,
          borderRadius: 2,
          bgcolor: 'action.disabledBackground',
          '& .MuiLinearProgress-bar': {
            bgcolor: warn ? 'warning.main' : color,
          },
        }}
      />
      <SparkLineChart
        data={values.length > 0 ? values : [0]}
        height={40}
        colors={[warn ? '#ffa726' : color]}
        showHighlight
        showTooltip
        sx={{ '& .MuiLineElement-root': { strokeWidth: 1.5 } }}
      />
    </Box>
  );
}

interface Props {
  cpuUsage:    DataPoint[];
  heapUsage:   DataPoint[];
  psramUsage:  DataPoint[];
}

export function SystemSparklines({ cpuUsage, heapUsage, psramUsage }: Props) {
  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary', fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase', fontSize: '0.7rem' }}>
        System Resources
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <GaugeSpark label="CPU"   data={cpuUsage}   color="#ab47bc" unit="%" warnAbove={80} />
        <GaugeSpark label="Heap"  data={heapUsage}  color="#26c6da" unit="%" warnAbove={85} />
        <GaugeSpark label="PSRAM" data={psramUsage} color="#9ccc65" unit="%" warnAbove={90} />
      </Box>
    </Box>
  );
}
