import { LineChart } from '@mui/x-charts/LineChart';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';
import { useContainerWidth, calcTickStep } from '../hooks/useContainerWidth';
import { HISTORY_WINDOW_MS } from '../hooks/useHistoryBuffer';

interface Props {
  coldHeadVolts:   DataPoint[];
  coldHeadAmps:    DataPoint[];
  systemVolts:     DataPoint[];
  systemAmps:      DataPoint[];
}

function toSeries(buf: DataPoint[]): number[] {
  return buf.map((p) => p.v);
}

function toXAxis(buf: DataPoint[]): number[] {
  return buf.map((p) => p.t);
}

function fmtTime(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

export function PowerChart({ coldHeadVolts, coldHeadAmps, systemVolts, systemAmps }: Props) {
  const [containerRef, containerWidth] = useContainerWidth<HTMLDivElement>();
  const tickStep = calcTickStep(containerWidth);

  const longest = [coldHeadVolts, coldHeadAmps, systemVolts, systemAmps]
    .reduce((a, b) => (a.length >= b.length ? a : b), []);
  const xData = toXAxis(longest);
  const n     = xData.length || 1;

  const xMax = longest.length > 0 ? longest[longest.length - 1].t : Date.now();
  const xMin = xMax - HISTORY_WINDOW_MS;

  const padTo = (arr: number[], len: number): (number | null)[] => {
    const out: (number | null)[] = [...arr];
    while (out.length < len) out.unshift(null);
    return out;
  };

  const series = [
    {
      label: 'Cold Head V',
      data: padTo(toSeries(coldHeadVolts), n),
      color: '#ce93d8',  // purple
      showMark: false,
    },
    {
      label: 'Cold Head A',
      data: padTo(toSeries(coldHeadAmps), n),
      color: '#f48fb1',  // pink
      showMark: false,
    },
    {
      label: 'System V',
      data: padTo(toSeries(systemVolts), n),
      color: '#80cbc4',  // teal
      showMark: false,
    },
    {
      label: 'System A',
      data: padTo(toSeries(systemAmps), n),
      color: '#ffcc80',  // light-orange
      showMark: false,
    },
  ];

  return (
    <Box ref={containerRef} sx={{ width: '100%', height: 260 }}>
      <Typography variant="subtitle2" sx={{ mb: 0.5, color: 'text.secondary', fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase', fontSize: '0.7rem' }}>
        Power Consumption
      </Typography>
      <LineChart
        xAxis={[{ data: xData.length > 0 ? xData : [xMax], min: xMin, max: xMax, scaleType: 'linear', valueFormatter: fmtTime, tickMinStep: tickStep }]}
        series={series}
        height={220}
        skipAnimation
        sx={{ '& .MuiChartsLegend-root': { fontSize: '0.7rem' } }}
        slotProps={{ legend: { position: { vertical: 'top', horizontal: 'right' }, itemMarkWidth: 10, itemMarkHeight: 10 } }}
        margin={{ top: 30, right: 10, bottom: 36, left: 52 }}
        grid={{ horizontal: true }}
      />
    </Box>
  );
}
