import { useState, useEffect, useCallback } from 'preact/hooks';
import CircularProgress from '@mui/material/CircularProgress';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { useTelemetry } from './hooks/useTelemetry';
import { useHistoryBuffer } from './hooks/useHistoryBuffer';
import { useFaultHistory } from './hooks/useFaultHistory';
import { Header } from './components/Header';
import { StatusPanel } from './components/StatusPanel';
import { FaultHistoryPanel } from './components/FaultHistoryPanel';
import { TemperatureChart } from './components/TemperatureChart';
import { PowerChart } from './components/PowerChart';
import { CoolingChart } from './components/CoolingChart';
import { AccelSparklines } from './components/AccelSparklines';
import { SystemSparklines } from './components/SystemSparklines';
import { ConsoleLog } from './components/ConsoleLog';
import type { TelemetryData } from './types/telemetry';
import { getField } from './types/telemetry';

// ─── MUI dark theme ───────────────────────────────────────────────────────────

const theme = createTheme({
  palette: {
    mode: 'light',
    primary:    { main: '#0277bd' },
    secondary:  { main: '#7b1fa2' },
    background: { default: '#eef2f7', paper: '#ffffff' },
    text:       { primary: '#1a2638', secondary: '#546e7a' },
    divider: 'rgba(0,0,0,0.10)',
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    fontSize: 13,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          scrollbarColor: '#b0bec5 #eef2f7',
          '&::-webkit-scrollbar': { width: 8 },
          '&::-webkit-scrollbar-thumb': { backgroundColor: '#b0bec5', borderRadius: 4 },
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
  'imu.roll_deg',
  'imu.pitch_deg',
  'imu.yaw_deg',
  'imu.accel_mag',
  'system.cpu_usage_percent',
  'system.heap_usage_percent',
  'system.psram_usage_percent',
] as const;

// ─── Quick-read tile data ─────────────────────────────────────────────────────

interface TileConfig {
  label: string;
  key:   string;
  unit:  string;
  dp:    number;
  color: string;
}

const TILES: TileConfig[] = [
  { label: 'Cold Head', key: 'cold_head.temp_c',         unit: '°C',   dp: 2, color: '#29b6f6' },
  { label: 'Ambient',   key: 'cold_head.ambient_temp_c', unit: '°C',   dp: 2, color: '#ffa726' },
  { label: 'Cool Rate', key: 'cold_head.cooling_rate',   unit: '°C/min',dp: 3, color: '#80cbc4' },
  { label: 'Sys V',     key: 'system.voltage_v',          unit: 'V',    dp: 2, color: '#ce93d8' },
  { label: 'Sys A',     key: 'system.current_a',         unit: 'A',    dp: 2, color: '#f48fb1' },
  { label: 'Sys W',     key: 'system.power_w',           unit: 'W',    dp: 1, color: '#ffcc80' },
  { label: 'Fan Speed', key: 'cooling.fan_speed',        unit: '%',    dp: 0, color: '#4dd0e1' },
];

// ─── App ──────────────────────────────────────────────────────────────────────

export function App() {
  const { data, status, frameCount, onData, onFaultHistory } = useTelemetry();
  const { push, getHistory }                                  = useHistoryBuffer([...HISTORY_KEYS]);
  const { faults, loading: faultsLoading, pushUpdate }        = useFaultHistory();

  // Trigger re-render on every incoming frame so charts update.
  const [tick, setTick] = useState(0);

  const handleFrame = useCallback((d: TelemetryData, ts: number) => {
    push(d, ts);
    setTick((n) => n + 1);
  }, [push]);

  useEffect(() => {
    onData(handleFrame);
  }, [onData, handleFrame]);

  useEffect(() => {
    onFaultHistory(pushUpdate);
  }, [onFaultHistory, pushUpdate]);

  // ── Loading screen ──────────────────────────────────────────────────────────
  // Show a spinner until the first telemetry frame arrives.  frameCount stays
  // at 0 for the entire blank-white period, so this fills that gap.

  if (frameCount === 0) {
    const loadingMsg =
      status === 'disconnected'
        ? 'Unable to reach device — retrying…'
        : 'Waiting for first telemetry frame…';

    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box
          sx={{
            minHeight: '100vh',
            bgcolor: 'background.default',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 2.5,
          }}
        >
          <CircularProgress size={52} thickness={3.5} />
          <Typography variant="h6" color="text.secondary" sx={{ fontWeight: 500 }}>
            Loading Dashboard
          </Typography>
          <Typography variant="caption" color="text.disabled">
            {loadingMsg}
          </Typography>
        </Box>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', display: 'flex', flexDirection: 'column' }}>

        {/* ── Header / status bar ────────────────────────────────────────── */}
        <Header
          connectionStatus={status}
          stateName={String(data.state?.name ?? '—')}
          statusText={String(data.state?.status_text ?? '')}
          onDuration={String(data.status?.on_duration ?? '')}
          timeInState={String(data.status?.time_in_state ?? '')}
          cooldownPct={typeof data.cold_head?.cooldown_pct === 'number' ? data.cold_head.cooldown_pct : undefined}
          frameCount={frameCount}
        />

        {/* ── Main content ───────────────────────────────────────────────── */}
        <Box sx={{ flex: 1, p: { xs: 1.5, sm: 2 }, position: 'relative' }}>

          {/* ── Connection-lost overlay ─────────────────────────────────── */}
          {status === 'disconnected' && (
            <Box
              sx={{
                position: 'absolute',
                inset: 0,
                zIndex: 50,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                bgcolor: 'rgba(238, 242, 247, 0.85)',
                backdropFilter: 'blur(2px)',
                gap: 1.5,
                borderRadius: 1,
              }}
            >
              <CircularProgress size={40} thickness={3} />
              <Typography variant="h6" color="text.secondary" sx={{ fontWeight: 600 }}>
                Connection Lost
              </Typography>
              <Typography variant="body2" color="text.disabled">
                Unable to reach device — reconnecting…
              </Typography>
            </Box>
          )}
          {/* MUI v7 Grid: use `size` prop instead of the deprecated `item` prop */}
          <Grid container spacing={2}>

            {/* ── Row 1: Status panel ──────────────────────────────────── */}
            <Grid size={{ xs: 12, sm: 12, md: 4, lg: 3 }}>
              <StatusPanel data={data} key={tick} />
              <Box sx={{ mt: 2 }}>
                <FaultHistoryPanel faults={faults} loading={faultsLoading} />
              </Box>
            </Grid>

            {/* ── Row 1 right: quick-read numeric tiles ────────────────── */}
            <Grid size={{ xs: 12, sm: 12, md: 8, lg: 9 }}>
              <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignContent: 'flex-start' }}>
                {TILES.map(({ label, key, unit, dp, color }) => {
                  const value = getField(data, key);
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
                />
              </Box>
            </Grid>

            <Grid size={{ xs: 12 }}>
              <Box sx={{ bgcolor: 'background.paper', borderRadius: 1, p: 1.5, border: '1px solid', borderColor: 'divider' }}>
                <CoolingChart
                  fanSpeed={getHistory('cooling.fan_speed')}
                  coolantTemp={getHistory('cooling.temp_c')}
                  flowRate={getHistory('cooling.flow_rate_lpm')}
                />
              </Box>
            </Grid>

            {/* ── Row 3: Sparkline panels ───────────────────────────────── */}
            <Grid size={{ xs: 12, md: 7 }}>
              <Box sx={{ bgcolor: 'background.paper', borderRadius: 1, p: 1.5, border: '1px solid', borderColor: 'divider' }}>
                <AccelSparklines
                  accelX={getHistory('imu.roll_deg')}
                  accelY={getHistory('imu.pitch_deg')}
                  accelZ={getHistory('imu.yaw_deg')}
                  accelMag={getHistory('imu.accel_mag')}
                  motion={typeof data.imu?.motion === 'number' ? data.imu.motion : undefined}
                />
              </Box>
            </Grid>

            <Grid size={{ xs: 12, md: 5 }}>
              <Box sx={{ bgcolor: 'background.paper', borderRadius: 1, p: 1.5, border: '1px solid', borderColor: 'divider' }}>
                <SystemSparklines
                  cpuUsage={getHistory('system.cpu_usage_percent')}
                  heapUsage={getHistory('system.heap_usage_percent')}
                  psramUsage={getHistory('system.psram_usage_percent')}
                />
              </Box>
            </Grid>

            {/* ── Console log panel ─────────────────────────────────────── */}
            <Grid size={{ xs: 12 }}>
              <Box sx={{ bgcolor: 'background.paper', borderRadius: 1, p: 1.5, border: '1px solid', borderColor: 'divider' }}>
                <ConsoleLog logEpoch={data.log_epoch} />
              </Box>
            </Grid>

          </Grid>
        </Box>
      </Box>
    </ThemeProvider>
  );
}
