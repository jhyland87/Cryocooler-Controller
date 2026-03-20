import type { TemperatureChartProps } from '../types/components';
import { TelemetryLineChart } from './TelemetryLineChart';

export function TemperatureChart({ actualC, ambientC, targetC }: TemperatureChartProps) {
  const series = [
    { label: 'Actual (°C)',  data: actualC,  color: '#1565c0' },
    { label: 'Ambient (°C)', data: ambientC, color: '#ffa726' },
    { label: 'Target (°C)',  data: targetC,  color: '#81d4fa', dashed: true },
  ];

  return (
    <TelemetryLineChart
      title=""
      series={series}
      yAxis={{}}
    />
  );
}
