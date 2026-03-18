import type { DataPoint } from '../types/telemetry';
import { TelemetryLineChart } from './TelemetryLineChart';

interface Props {
  actualC:  DataPoint[];
  ambientC: DataPoint[];
}

export function TemperatureChart({ actualC, ambientC }: Props) {
  const series = [
    { label: 'Actual (°C)',    data: actualC,  color: '#29b6f6' },
    { label: 'Ambient (°C)',   data: ambientC, color: '#ffa726' },

  ];

  return (
    <TelemetryLineChart
      title=""
      series={series}
      yAxis={{ min: -200, max: 40 }}
    />
  );
}
