import { useState, useEffect, useCallback } from 'preact/hooks';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { useTelemetry } from './hooks/useTelemetry';
import { useHistoryBuffer } from './hooks/useHistoryBuffer';
import { Header } from './components/Header';
import { StatusPanel } from './components/StatusPanel';
import { TemperatureChart } from './components/TemperatureChart';
import { PowerChart } from './components/PowerChart';
import { CoolingChart } from './components/CoolingChart';
import { AccelSparklines } from './components/AccelSparklines';
import { SystemSparklines } from './components/SystemSparklines';
import type { TelemetryData } from './types/telemetry';

// ─── MUI dark theme ───────────────────────────────────────────────────────────

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary:    { main: '#29b6f6' },
    secondary:  { main: '#ce93d8' },
    background: { default: '#0a0e14', paper: '#111820' },
    text:       { primary: '#e1e8f0', secondary: '#8899aa' },
    divider: 'rgba(255,255,255,0.08)',
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    fontSize: 13,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          scrollbarColor: '#2a3340 #111820',
          '&::-webkit-scrollbar': { width: 8 },
          '&::-webkit-scrollbar-thumb': { backgroundColor: '#2a3340', borderRadius: 4 },
        },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
    },
  },
});

// ─── History buffer keys ──────────────────────────────────────────────────────

const HISTORY_KEYS = [
  'cold_head.temp_c',
  'cold_head.ambient_temp_c',
  'cold_head.delta_below_ambient_c',
  'cold_head.voltage_v',
  'cold_head.current_a',
  'system.voltage_v',
  'system.current_a',
  'cooling.fan_speed',
  'cooling.temp_c',
  'cooling.flow_rate_lpm',
  'imu.x',
  'imu.y',
  'imu.z',
  'imu.accel_mag',
  'system.cpu_usage_percent',
  'system.heap_usage_percent',
  'system.psram_usage_percent',
] as const;

// ─── Quick-read tile data ─────────────────────────────────────────────────────

interface TileConfig {
  label: string;
  key:   keyof TelemetryData;
  unit:  string;
  dp:    number;
  color: string;
}

const TILES: TileConfig[] = [
  { label: 'Cold Head', key: 'cold_head.temp_c',         unit: '°C',   dp: 2, color: '#29b6f6' },
  { label: 'Ambient',   key: 'cold_head.ambient_temp_c', unit: '°C',   dp: 2, color: '#ffa726' },
  { label: 'Cold Head', key: 'cold_head.temp_k',         unit: 'K',    dp: 2, color: '#4fc3f7' },
  { label: 'Cool Rate', key: 'cold_head.cooling_rate',   unit: 'K/min',dp: 3, color: '#80cbc4' },
  { label: 'Sys V',     key: 'system.voltage_v',         unit: 'V',    dp: 2, color: '#ce93d8' },
  { label: 'Sys A',     key: 'system.current_a',         unit: 'A',    dp: 2, color: '#f48fb1' },
  { label: 'Sys W',     key: 'system.power_w',           unit: 'W',    dp: 1, color: '#ffcc80' },
  { label: 'Fan Speed', key: 'cooling.fan_speed',        unit: '%',    dp: 0, color: '#4dd0e1' },
];

// ─── App ──────────────────────────────────────────────────────────────────────

export function App() {
  const { data, status, frameCount, onData } = useTelemetry();
  const { push, getHistory }                  = useHistoryBuffer([...HISTORY_KEYS]);

  // Trigger re-render on every incoming frame so charts update.
  const [tick, setTick] = useState(0);

  const handleFrame = useCallback((d: TelemetryData, ts: number) => {
    push(d, ts);
    setTick((n) => n + 1);
  }, [push]);

  useEffect(() => {
    onData(handleFrame);
  }, [onData, handleFrame]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', display: 'flex', flexDirection: 'column' }}>

        {/* ── Header / status bar ────────────────────────────────────────── */}
        <Header
          connectionStatus={status}
          stateName={String(data['state.name'] ?? '—')}
          statusText={String(data['state.status_text'] ?? '')}
          onDuration={String(data['status.on_duration'] ?? '')}
          timeInState={String(data['status.time_in_state'] ?? '')}
          cooldownPct={typeof data['cold_head.cooldown_pct'] === 'number' ? data['cold_head.cooldown_pct'] : undefined}
          frameCount={frameCount}
        />

        {/* ── Main content ───────────────────────────────────────────────── */}
        <Box sx={{ flex: 1, p: { xs: 1.5, sm: 2 } }}>
          {/* MUI v7 Grid: use `size` prop instead of the deprecated `item` prop */}
          <Grid container spacing={2}>

            {/* ── Row 1: Status panel ──────────────────────────────────── */}
            <Grid size={{ xs: 12, sm: 12, md: 4, lg: 3 }}>
              <StatusPanel data={data} key={tick} />
            </Grid>

            {/* ── Row 1 right: quick-read numeric tiles ────────────────── */}
            <Grid size={{ xs: 12, sm: 12, md: 8, lg: 9 }}>
              <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignContent: 'flex-start' }}>
                {TILES.map(({ label, key, unit, dp, color }) => {
                  const value = data[key];
                  return (
                    <Box
                      key={`${label}-${unit}`}
                      sx={{
                        flex: '1 1 90px',
                        minWidth: 80,
                        bgcolor: 'background.paper',
                        borderRadius: 1,
                        p: 1.25,
                        border: '1px solid',
                        borderColor: 'divider',
                        textAlign: 'center',
                      }}
                    >
                      <Typography
                        sx={{ fontSize: '1.2rem', fontWeight: 700, color, lineHeight: 1.1, fontFamily: 'monospace' }}
                      >
                        {typeof value === 'number' ? value.toFixed(dp) : '—'}
                      </Typography>
                      <Typography variant="caption" sx={{ color: 'text.disabled', fontSize: '0.6rem', display: 'block' }}>
                        {unit}
                      </Typography>
                      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.62rem', letterSpacing: 0.5, textTransform: 'uppercase' }}>
                        {label}
                      </Typography>
                    </Box>
                  );
                })}
              </Box>
            </Grid>

            {/* ── Row 2: Main line charts ───────────────────────────────── */}
            <Grid size={{ xs: 12, md: 6 }}>
              <Box sx={{ bgcolor: 'background.paper', borderRadius: 1, p: 1.5, border: '1px solid', borderColor: 'divider' }}>
                <TemperatureChart
                  actualC={getHistory('cold_head.temp_c')}
                  ambientC={getHistory('cold_head.ambient_temp_c')}
                  deltaC={getHistory('cold_head.delta_below_ambient_c')}
                  key={`temp-${tick}`}
                />
              </Box>
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <Box sx={{ bgcolor: 'background.paper', borderRadius: 1, p: 1.5, border: '1px solid', borderColor: 'divider' }}>
                <PowerChart
                  coldHeadVolts={getHistory('cold_head.voltage_v')}
                  coldHeadAmps={getHistory('cold_head.current_a')}
                  systemVolts={getHistory('system.voltage_v')}
                  systemAmps={getHistory('system.current_a')}
                  key={`power-${tick}`}
                />
              </Box>
            </Grid>

            <Grid size={{ xs: 12 }}>
              <Box sx={{ bgcolor: 'background.paper', borderRadius: 1, p: 1.5, border: '1px solid', borderColor: 'divider' }}>
                <CoolingChart
                  fanSpeed={getHistory('cooling.fan_speed')}
                  coolantTemp={getHistory('cooling.temp_c')}
                  flowRate={getHistory('cooling.flow_rate_lpm')}
                  key={`cooling-${tick}`}
                />
              </Box>
            </Grid>

            {/* ── Row 3: Sparkline panels ───────────────────────────────── */}
            <Grid size={{ xs: 12, md: 7 }}>
              <Box sx={{ bgcolor: 'background.paper', borderRadius: 1, p: 1.5, border: '1px solid', borderColor: 'divider' }}>
                <AccelSparklines
                  accelX={getHistory('imu.x')}
                  accelY={getHistory('imu.y')}
                  accelZ={getHistory('imu.z')}
                  accelMag={getHistory('imu.accel_mag')}
                  motion={typeof data['imu.motion'] === 'number' ? data['imu.motion'] : undefined}
                  key={`accel-${tick}`}
                />
              </Box>
            </Grid>

            <Grid size={{ xs: 12, md: 5 }}>
              <Box sx={{ bgcolor: 'background.paper', borderRadius: 1, p: 1.5, border: '1px solid', borderColor: 'divider' }}>
                <SystemSparklines
                  cpuUsage={getHistory('system.cpu_usage_percent')}
                  heapUsage={getHistory('system.heap_usage_percent')}
                  psramUsage={getHistory('system.psram_usage_percent')}
                  key={`sys-${tick}`}
                />
              </Box>
            </Grid>

          </Grid>
        </Box>
      </Box>
    </ThemeProvider>
  );
}
