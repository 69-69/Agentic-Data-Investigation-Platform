"use client";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
const theme = createTheme({
  palette: {
    primary: { main: "#087b70", dark: "#065e56" },
    secondary: { main: "#172b42" },
    background: { default: "#f5f7f9", paper: "#fff" },
    text: { primary: "#172b42", secondary: "#526477" },
  },
  typography: {
    fontFamily: "Arial, Helvetica, sans-serif",
    h1: { fontSize: "2.35rem", fontWeight: 700, letterSpacing: "-.055em" },
    h2: { fontSize: "1.35rem", fontWeight: 700, letterSpacing: "-.025em" },
    h3: { fontSize: "1.05rem", fontWeight: 700 },
    button: { textTransform: "none", fontWeight: 600 },
    body2: { lineHeight: 1.65 },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiPaper: { defaultProps: { elevation: 0 } },
    MuiTab: {
      styleOverrides: { root: { textTransform: "none", fontWeight: 600 } },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
  },
});
export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}
