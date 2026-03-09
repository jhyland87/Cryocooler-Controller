import { SparkLineChart } from '@mui/x-charts/SparkLineChart';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import type { DataPoint } from '../types/telemetry';

interface SparkProps {
  label:  string;
  data:   DataPoint[];
  color:  string;
  unit:   string;
}

function SparkItem({ label, data, color, unit }: SparkProps) {
  const values = data.map((p) => p.v);
  const last   = values.length > 0 ? values[values.length - 1] : null;

  return (
    <Box sx={{
      flex: '1 1 140px',
      minWidth: 120,
      bgcolor: 'background.paper',
      borderRadius: 1,
      p: 1.5,
      border: '1px solid',
      borderColor: 'divider',
    }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.8, fontSize: '0.65rem' }}>
          {label}
        </Typography>
        {last !== null && (
          <Typography variant="caption" sx={{ color, fontWeight: 700, fontSize: '0.75rem' }}>
            {last.toFixed(3)} {unit}
          </Typography>
        )}
      </Box>
      <SparkLineChart
        data={values.length > 0 ? values : [0]}
        height={50}
        colors={[color]}
        showHighlight
        showTooltip
        sx={{ '& .MuiLineElement-root': { strokeWidth: 1.5 } }}
      />
    </Box>
  );
}

interface Props {
  accelX:    DataPoint[];
  accelY:    DataPoint[];
  accelZ:    DataPoint[];
  accelMag:  DataPoint[];
  motion:    number | undefined;
}

export function AccelSparklines({ accelX, accelY, accelZ, accelMag, motion }: Props) {
  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <Typography variant="subtitle2" sx={{ color: 'text.secondary', fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase', fontSize: '0.7rem' }}>
          Accelerometer
        </Typography>
        <Chip
          label={motion ? 'MOTION' : 'STILL'}
          size="small"
          sx={{
            fontSize: '0.6rem',
            height: 18,
            bgcolor: motion ? 'warning.dark' : 'success.dark',
            color: '#fff',
            fontWeight: 700,
            letterSpacing: 0.8,
          }}
        />
      </Box>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <SparkItem label="Roll"      data={accelX}   color="#ef5350" unit="°" />
        <SparkItem label="Pitch"     data={accelY}   color="#42a5f5" unit="°" />
        <SparkItem label="Yaw"       data={accelZ}   color="#66bb6a" unit="°" />
        <SparkItem label="Magnitude" data={accelMag} color="#ffa726" unit="m/s²" />
      </Box>
    </Box>
  );
}
