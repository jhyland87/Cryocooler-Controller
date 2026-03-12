import { LineChart } from '@mui/x-charts/LineChart';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { DataPoint } from '../types/telemetry';
import { useContainerWidth, calcTickStep } from '../hooks/useContainerWidth';
import { HISTORY_WINDOW_MS } from '../hooks/useHistoryBuffer';
import { createTimeFormatter } from '../utils/formatters';
import { useMemo } from 'preact/hooks';

interface Props {
  actualC:  DataPoint[];
  ambientC: DataPoint[];
  /** Optional delta-below-ambient series. */
  deltaC?:  DataPoint[];
}

function toSeries(buf: DataPoint[]): number[] {
  return buf.map((p) => p.v);
}

/** Returns raw ms-epoch values for use as an absolute time x-axis. */
function toXAxis(buf: DataPoint[]): number[] {
  return buf.map((p) => p.t);
}

export function TemperatureChart({ actualC, ambientC, deltaC }: Props) {
  const [containerRef, containerWidth] = useContainerWidth<HTMLDivElement>();
  const tickStep = calcTickStep(containerWidth);

  const longest = actualC.length >= ambientC.length ? actualC : ambientC;
  const xData   = toXAxis(longest);
  const timeFormatter = useMemo(() => createTimeFormatter(), [xData]);

  const n       = xData.length || 1;

  // Pin the x-axis to a fixed rolling window so the domain never rescales as
  // the buffer fills — it only slides forward.  Lines grow in from the left
  // edge rather than appearing to expand from the centre.
  const xMax = longest.length > 0 ? longest[longest.length - 1].t : Date.now();
  const xMin = xMax - HISTORY_WINDOW_MS;

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
    <Box ref={containerRef} sx={{ width: '100%', height: 260 }}>
      <Typography variant="subtitle2" sx={{
        mb: 0.5,
        color: 'text.secondary',
        fontWeight: 600,
        letterSpacing: 1,
        textTransform: 'uppercase',
        fontSize: '0.7rem'
      }}>
        Cold Head Temperature
      </Typography>
      <LineChart
        xAxis={[{
          data: xData.length > 0 ? xData : [xMax],
          min: xMin,
          max: xMax,
          scaleType: 'linear',
          valueFormatter: timeFormatter,
          tickMinStep: tickStep
        }]}
        yAxis={[{
          min: -200,
          max: 40,
          valueFormatter: (v: number) => v % 1 === 0 ? String(v) : v.toFixed(1) }]}
        series={series}
        height={220}
        skipAnimation
        sx={{
          '& .MuiChartsLegend-root': { fontSize: '0.7rem' },
        }}
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
