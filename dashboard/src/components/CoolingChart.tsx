import { LineChart } from '@mui/x-charts/LineChart';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';

interface Props {
  fanSpeed:     DataPoint[];  // 0–100 %
  coolantTemp:  DataPoint[];  // °C
  flowRate:     DataPoint[];  // L/min
}

function toSeries(buf: DataPoint[]): number[] {
  return buf.map((p) => p.v);
}

function toXAxis(buf: DataPoint[]): number[] {
  if (buf.length === 0) return [];
  const t0 = buf[0].t;
  return buf.map((p) => Math.round((p.t - t0) / 1000));
}

export function CoolingChart({ fanSpeed, coolantTemp, flowRate }: Props) {
  const longest = [fanSpeed, coolantTemp, flowRate]
    .reduce((a, b) => (a.length >= b.length ? a : b), []);
  const xData = toXAxis(longest);
  const n     = xData.length || 1;

  const padTo = (arr: number[], len: number): (number | null)[] => {
    const out: (number | null)[] = [...arr];
    while (out.length < len) out.unshift(null);
    return out;
  };

  const series = [
    {
      label: 'Fan Speed (%)',
      data: padTo(toSeries(fanSpeed), n),
      color: '#4dd0e1',   // cyan
      showMark: false,
    },
    {
      label: 'Coolant Temp (°C)',
      data: padTo(toSeries(coolantTemp), n),
      color: '#ef9a9a',   // red-ish
      showMark: false,
    },
    {
      label: 'Flow (L/min)',
      data: padTo(toSeries(flowRate), n),
      color: '#a5d6a7',   // light-green
      showMark: false,
    },
  ];

  return (
    <Box sx={{ width: '100%', height: 260 }}>
      <Typography variant="subtitle2" sx={{ mb: 0.5, color: 'text.secondary', fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase', fontSize: '0.7rem' }}>
        Cooling System
      </Typography>
      <LineChart
        xAxis={[{ data: xData.length > 0 ? xData : [0], label: 'Time (s)', scaleType: 'linear' }]}
        series={series}
        height={220}
        sx={{ '& .MuiChartsLegend-root': { fontSize: '0.7rem' } }}
        slotProps={{ legend: { position: { vertical: 'top', horizontal: 'right' }, itemMarkWidth: 10, itemMarkHeight: 10 } }}
        margin={{ top: 30, right: 10, bottom: 36, left: 52 }}
        grid={{ horizontal: true }}
      />
    </Box>
  );
}
