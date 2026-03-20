import Box from '@mui/material/Box';
import { SparkCard } from './SparkCard';
import type { SystemSparklinesProps } from '../types/components';
import * as sx from '../theme/styles';

export function SystemSparklines({ cpuUsage, heapUsage, psramUsage }: SystemSparklinesProps) {
  return (
    <Box>
      <Box sx={sx.sparkWrapRow}>
        <SparkCard label="CPU"   data={cpuUsage}   color="#ab47bc" unit="%" gauge={{ warnAbove: 80  }} />
        <SparkCard label="Heap"  data={heapUsage}  color="#26c6da" unit="%" gauge={{ warnAbove: 85  }} />
        <SparkCard label="PSRAM" data={psramUsage} color="#9ccc65" unit="%" gauge={{ warnAbove: 90  }} />
      </Box>
    </Box>
  );
}
