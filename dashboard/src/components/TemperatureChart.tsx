import { LineChart } from '@mui/x-charts/LineChart';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';

interface Props {
  actualC:  DataPoint[];
  ambientC: DataPoint[];
  /** Optional delta-below-ambient series. */
  deltaC?:  DataPoint[];
}

function toSeries(buf: DataPoint[]): number[] {
  return buf.map((p) => p.v);
}

function toXAxis(buf: DataPoint[]): number[] {
  if (buf.length === 0) return [];
  const t0 = buf[0].t;
  return buf.map((p) => Math.round((p.t - t0) / 1000));
}

export function TemperatureChart({ actualC, ambientC, deltaC }: Props) {
  const xData = toXAxis(actualC.length >= ambientC.length ? actualC : ambientC);
  const n     = xData.length || 1;

  const padTo = (arr: number[], len: number): (number | null)[] => {
    const out: (number | null)[] = [...arr];
    while (out.length < len) out.unshift(null);
    return out;
  };

  const series = [
    {
      label: 'Actual (°C)',
      data: padTo(toSeries(actualC), n),
      color: '#29b6f6',  // light-blue
      showMark: false,
    },
    {
      label: 'Ambient (°C)',
      data: padTo(toSeries(ambientC), n),
      color: '#ffa726',  // amber
      showMark: false,
    },
    ...(deltaC && deltaC.length > 0
      ? [{
          label: 'Δ Below Ambient',
          data: padTo(toSeries(deltaC), n),
          color: '#66bb6a',  // green
          showMark: false,
        }]
      : []),
  ];

  return (
    <Box sx={{ width: '100%', height: 260 }}>
      <Typography variant="subtitle2" sx={{ mb: 0.5, color: 'text.secondary', fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase', fontSize: '0.7rem' }}>
        Cold Head Temperature
      </Typography>
      <LineChart
        xAxis={[{ data: xData.length > 0 ? xData : [0], label: 'Time (s)', scaleType: 'linear' }]}
        series={series}
        height={220}
        sx={{
          '& .MuiChartsLegend-root': { fontSize: '0.7rem' },
        }}
        slotProps={{ legend: { position: { vertical: 'top', horizontal: 'right' }, itemMarkWidth: 10, itemMarkHeight: 10 } }}
        margin={{ top: 30, right: 10, bottom: 36, left: 52 }}
        grid={{ horizontal: true }}
      />
    </Box>
  );
}
