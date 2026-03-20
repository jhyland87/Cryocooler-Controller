import { createTheme } from '@mui/material/styles';

// ─── MUI Theme ──────────────────────────────────────────────────────────────

export const theme = createTheme({
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
