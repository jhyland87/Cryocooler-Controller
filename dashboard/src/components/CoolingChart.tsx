import { LineChart } from '@mui/x-charts/LineChart';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';
import { useContainerWidth, calcTickStep } from '../hooks/useContainerWidth';
import { HISTORY_WINDOW_MS } from '../hooks/useHistoryBuffer';
import { createTimeFormatter } from '../utils/formatters';
import { useMemo } from 'preact/hooks';

interface Props {
  fanSpeed:     DataPoint[];  // 0–100 %
  coolantTemp:  DataPoint[];  // °C
  flowRate:     DataPoint[];  // L/min
}

function toSeries(buf: DataPoint[]): number[] {
  return buf.map((p) => p.v);
}

function toXAxis(buf: DataPoint[]): number[] {
  return buf.map((p) => p.t);
}

export function CoolingChart({ fanSpeed, coolantTemp, flowRate }: Props) {
  const [containerRef, containerWidth] = useContainerWidth<HTMLDivElement>();
  const tickStep = calcTickStep(containerWidth);


  const longest = [fanSpeed, coolantTemp, flowRate]
    .reduce((a, b) => (a.length >= b.length ? a : b), []);
  const xData = toXAxis(longest);
  const timeFormatter = useMemo(() => createTimeFormatter(), [xData]);
  const n     = xData.length || 1;

  const xMax = longest.length > 0 ? longest[longest.length - 1].t : Date.now();
  const xMin = xMax - HISTORY_WINDOW_MS;

  const rawYMax = Math.max(0, ...fanSpeed.map((p) => p.v), ...coolantTemp.map((p) => p.v), ...flowRate.map((p) => p.v));
  const yMax = rawYMax > 0 ? undefined : 1;

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
    <Box ref={containerRef} sx={{ width: '100%', height: 260 }}>
      <Typography variant="subtitle2" sx={{
        mb: 0.5,
        color: 'text.secondary',
        fontWeight: 600,
        letterSpacing: 1,
        textTransform: 'uppercase',
        fontSize: '0.7rem'
      }}>
        Cooling System
      </Typography>
      <LineChart
        xAxis={[{
          data: xData.length > 0 ? xData : [xMax],
          min: xMin,
          max: xMax,
          scaleType: 'linear',
          valueFormatter: timeFormatter,
          tickMinStep: tickStep,
          tickLabelStyle: {
            //angle: 45, // Use angle for automatic, or transformation for custom
            textAnchor: 'start',
            //transform: 'rotateZ(45deg)', // Rotate labels 45 degrees [1]
            fontSize: 12,
          },
        }]}
        yAxis={[{
          min: 0,
          max: yMax,
          valueFormatter: (v: number) => v % 1 === 0 ? String(v) : v.toFixed(1)
        }]}
        series={series}
        height={220}
        skipAnimation
        sx={{ '& .MuiChartsLegend-root': { fontSize: '0.7rem' } }}
        slotProps={{
          legend: {
            position: {
              vertical: 'top',
              horizontal: 'right'
            },
            itemMarkWidth: 10,
            itemMarkHeight: 10
          }
        }}
        margin={{
          top: 30,
          right: 10,
          bottom: 36,
          left: 52
        }}
        grid={{ horizontal: true }}
      />
    </Box>
  );
}
