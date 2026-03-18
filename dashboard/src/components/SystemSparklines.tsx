import Box from '@mui/material/Box';
import type { DataPoint } from '../types/telemetry';
import { SparkCard } from './SparkCard';

interface Props {
  cpuUsage:   DataPoint[];
  heapUsage:  DataPoint[];
  psramUsage: DataPoint[];
}

export function SystemSparklines({ cpuUsage, heapUsage, psramUsage }: Props) {
  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <SparkCard label="CPU"   data={cpuUsage}   color="#ab47bc" unit="%" gauge={{ warnAbove: 80  }} />
        <SparkCard label="Heap"  data={heapUsage}  color="#26c6da" unit="%" gauge={{ warnAbove: 85  }} />
        <SparkCard label="PSRAM" data={psramUsage} color="#9ccc65" unit="%" gauge={{ warnAbove: 90  }} />
      </Box>
    </Box>
  );
}
