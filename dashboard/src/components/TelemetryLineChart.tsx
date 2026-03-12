import { LineChart } from '@mui/x-charts/LineChart';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useMemo } from 'preact/hooks';
import type { DataPoint } from '../types/telemetry';
import { useContainerWidth, calcTickStep } from '../hooks/useContainerWidth';
import { HISTORY_WINDOW_MS } from '../hooks/useHistoryBuffer';
import { createTimeFormatter } from '../utils/formatters';

// ─── Public API ───────────────────────────────────────────────────────────────

export interface ChartSeries {
  label: string;
  data:  DataPoint[];
  color: string;
}

export interface TelemetryLineChartProps {
  title:  string;
  series: ChartSeries[];
  /**
   * Y-axis bounds.
   *
   * • Both `min` and `max` present  — fixed domain (e.g. temperature: -200..40).
   * • Only `min` present            — `max` is computed from live data, with a
   *                                   fallback of `1` when all values are zero
   *                                   so the axis never collapses to [0, 0].
   * • Omitted entirely              — fully auto-scaled by MUI.
   */
  yAxis?: {
    min?: number;
    max?: number;
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Pad a series array to `len` by prepending nulls (aligns shorter series to
 *  the right when the longest series has earlier data points). */
function padTo(arr: number[], len: number): (number | null)[] {
  const out: (number | null)[] = [...arr];
  while (out.length < len) out.unshift(null);
  return out;
}

// ─── Component ────────────────────────────────────────────────────────────────

/**
 * TelemetryLineChart
 *
 * Shared rolling time-series chart used by TemperatureChart, PowerChart, and
 * CoolingChart.  Callers supply a title, an array of series configs, and
 * optional y-axis bounds; everything else (x-axis window, time formatter,
 * container-responsive tick step, legend, margins) is handled here.
 */
export function TelemetryLineChart({ title, series, yAxis }: TelemetryLineChartProps) {
  const [containerRef, containerWidth] = useContainerWidth<HTMLDivElement>();
  const tickStep = calcTickStep(containerWidth);

  // Use whichever series is longest as the shared x-axis source.
  const longest = series.reduce<DataPoint[]>(
    (best, s) => (s.data.length >= best.length ? s.data : best),
    [],
  );

  const xData        = longest.map((p) => p.t);
  // Recreate the formatter only when the x-axis data changes.
  const timeFormatter = useMemo(() => createTimeFormatter(), [xData.length > 0 ? xData[0] : 0]);

  const n    = xData.length || 1;
  const xMax = longest.length > 0 ? longest[longest.length - 1].t : Date.now();
  const xMin = xMax - HISTORY_WINDOW_MS;

  // Compute a dynamic y-axis ceiling when the caller hasn't pinned `max`.
  // If there is positive data, pass `undefined` so MUI auto-scales; when all
  // values are zero, pass `1` so the axis doesn't degenerate to [0, 0].
  const yMax: number | undefined = (() => {
    if (yAxis?.max !== undefined) return yAxis.max;
    const allValues = series.flatMap((s) => s.data.map((p) => p.v));
    const raw = allValues.length > 0 ? Math.max(0, ...allValues) : 0;
    return raw > 0 ? undefined : 1;
  })();

  const chartSeries = series.map((s) => ({
    label:    s.label,
    data:     padTo(s.data.map((p) => p.v), n),
    color:    s.color,
    showMark: false,
  }));

  return (
    <Box ref={containerRef} sx={{ width: '100%', height: 260 }}>
      <Typography
        variant="subtitle2"
        sx={{
          mb: 0.5,
          color: 'text.secondary',
          fontWeight: 600,
          letterSpacing: 1,
          textTransform: 'uppercase',
          fontSize: '0.7rem',
        }}
      >
        {title}
      </Typography>

      <LineChart
        xAxis={[{
          data:           xData.length > 0 ? xData : [xMax],
          min:            xMin,
          max:            xMax,
          scaleType:      'linear',
          valueFormatter: timeFormatter,
          tickMinStep:    tickStep,
        }]}
        yAxis={[{
          min:            yAxis?.min,
          max:            yMax,
          valueFormatter: (v: number) => v % 1 === 0 ? String(v) : v.toFixed(1),
        }]}
        series={chartSeries}
        height={220}
        skipAnimation
        sx={{ '& .MuiChartsLegend-root': { fontSize: '0.7rem' } }}
        slotProps={{
          legend: {
            position:       { vertical: 'top', horizontal: 'right' },
            itemMarkWidth:  10,
            itemMarkHeight: 10,
          },
        }}
        margin={{ top: 30, right: 10, bottom: 36, left: 52 }}
        grid={{ horizontal: true }}
      />
    </Box>
  );
}
