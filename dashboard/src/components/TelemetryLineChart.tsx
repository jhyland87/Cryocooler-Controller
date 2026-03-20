import { LineChart } from '@mui/x-charts/LineChart';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useMemo, useState, useCallback } from 'preact/hooks';
import type { DataPoint } from '../types/telemetry';
import { useContainerWidth, calcTickStep } from '../hooks/useContainerWidth';
import { HISTORY_WINDOW_MS } from '../hooks/useHistoryBuffer';
import { createTimeFormatter } from '../utils/formatters';
import * as sx from '../theme/styles';

// ─── Public API ───────────────────────────────────────────────────────────────

export interface ChartSeries {
  label: string;
  data:  DataPoint[];
  color: string;
}

export interface TelemetryLineChartProps {
  title:  string;
  series: ChartSeries[];
  yAxis?: {
    min?: number;
    max?: number;
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function padTo(arr: number[], len: number): (number | null)[] {
  const out: (number | null)[] = [...arr];
  while (out.length < len) out.unshift(null);
  return out;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function TelemetryLineChart({ title, series, yAxis }: TelemetryLineChartProps) {
  const [containerRef, containerWidth] = useContainerWidth<HTMLDivElement>();
  const tickStep = calcTickStep(containerWidth);
  const [hidden, setHidden] = useState<Set<string>>(() => new Set());

  const toggleSeries = useCallback((label: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  }, []);

  const visibleSeries = series.filter((s) => !hidden.has(s.label));

  const longest = series.reduce<DataPoint[]>(
    (best, s) => (s.data.length >= best.length ? s.data : best),
    [],
  );

  const xData        = longest.map((p) => p.t);
  const timeFormatter = useMemo(() => createTimeFormatter(), [xData.length > 0 ? xData[0] : 0]);

  const n    = xData.length || 1;
  const xMax = longest.length > 0 ? longest[longest.length - 1].t : Date.now();
  const xMin = xMax - HISTORY_WINDOW_MS;

  const someHidden = hidden.size > 0;

  const yMin: number | undefined = (() => {
    if (visibleSeries.length === 0) return yAxis?.min ?? 0;
    if (!someHidden && yAxis?.min !== undefined) return yAxis.min;
    return yAxis?.min !== undefined ? undefined : undefined;
  })();

  const yMax: number | undefined = (() => {
    if (visibleSeries.length === 0) return yAxis?.max ?? 1;
    if (!someHidden && yAxis?.max !== undefined) return yAxis.max;
    const allValues = visibleSeries.flatMap((s) => s.data.map((p) => p.v));
    const raw = allValues.length > 0 ? Math.max(0, ...allValues) : 0;
    return raw > 0 ? undefined : 1;
  })();

  const chartSeries = visibleSeries.map((s) => ({
    label:    s.label,
    data:     padTo(s.data.map((p) => p.v), n),
    color:    s.color,
    showMark: false,
  }));

  return (
    <Box ref={containerRef} sx={sx.chartContainer}>
      <Box sx={sx.chartLegendRow}>
        {title && (
          <Typography variant="subtitle2" sx={sx.chartTitle}>
            {title}
          </Typography>
        )}
        {series.map((s) => {
          const isVisible = !hidden.has(s.label);
          return (
            <Box
              key={s.label}
              onClick={() => toggleSeries(s.label)}
              sx={sx.legendToggle(isVisible, s.color)}
            >
              <Box sx={sx.legendDotSmall(isVisible, s.color)} />
              <Typography sx={sx.legendToggleLabel(isVisible)}>
                {s.label}
              </Typography>
            </Box>
          );
        })}
      </Box>

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
          min:            yMin,
          max:            yMax,
          valueFormatter: (v: number) => v % 1 === 0 ? String(v) : v.toFixed(1),
        }]}
        series={chartSeries}
        height={220}
        skipAnimation
        slotProps={{ legend: { hidden: true } }}
        margin={{ top: 10, right: 10, bottom: 36, left: 52 }}
        grid={{ horizontal: true }}
      />
    </Box>
  );
}
