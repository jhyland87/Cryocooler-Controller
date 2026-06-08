import type { CoolingChartProps } from '../types/components';
import { TelemetryLineChart } from './TelemetryLineChart';

export function CoolingChart({ fanSpeed, coolantTemp, flowRate, overlays }: CoolingChartProps) {
  const series = [
    { label: 'Fan Speed (%)',     data: fanSpeed,    color: '#4dd0e1' },
    { label: 'Coolant Temp (°C)', data: coolantTemp, color: '#ef9a9a' },
    { label: 'Flow (L/min)',      data: flowRate,    color: '#a5d6a7' },
  ];

  return (
    <TelemetryLineChart
      title=""
      series={series}
      yAxis={{  }}
      overlays={overlays}
    />
  );
}
