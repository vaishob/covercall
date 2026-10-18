import { createTheme, Theme } from '@mui/material/styles';

export interface CoverCallColorTokens {
  canvas: string;
  surface: string;
  surfaceElevated: string;
  surfaceSubtle: string;
  surfaceMutedRejected: string;
  borderSubtle: string;
  borderStrong: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  brandPrimary: string;
  brandPrimaryHover: string;
  brandContrastText: string;
  legalPassBg: string;
  legalPassText: string;
  legalPassBorder: string;
  ruleWarnBg: string;
  ruleWarnText: string;
  ruleWarnBorder: string;
  amberAlertBg: string;
  amberAlertText: string;
  amberAlertBorder: string;
  focusRing: string;
}

export const LIGHT_TOKENS: CoverCallColorTokens = {
  canvas: '#F5F6F3', // Warm architectural stone neutral (<4% saturation)
  surface: '#FFFFFF',
  surfaceElevated: '#FFFFFF',
  surfaceSubtle: '#ECEEE9',
  surfaceMutedRejected: '#F1F2EE',
  borderSubtle: '#D5D9D0',
  borderStrong: '#8C9484',
  textPrimary: '#111612', // 16.8:1 on white
  textSecondary: '#374139', // 9.6:1 on white
  textMuted: '#4E5B51', // 6.5:1 on white (exceeds WCAG AA 4.5:1)
  brandPrimary: '#0B4F3F', // Deep Singapore transit emerald — 9.1:1 with white text
  brandPrimaryHover: '#073B2F',
  brandContrastText: '#FFFFFF',
  legalPassBg: '#E6F4EE',
  legalPassText: '#0A4B39', // 8.4:1 contrast on legalPassBg
  legalPassBorder: '#8CC7B3',
  ruleWarnBg: '#FDF1F0',
  ruleWarnText: '#8A1C14', // 7.9:1 contrast on ruleWarnBg
  ruleWarnBorder: '#E5A39E',
  amberAlertBg: '#FEF5E7',
  amberAlertText: '#6E3B00', // 7.5:1 contrast on amberAlertBg
  amberAlertBorder: '#E6B87A',
  focusRing: '#0B57D0',
};

export const DARK_TOKENS: CoverCallColorTokens = {
  canvas: '#0C100E',
  surface: '#141B18',
  surfaceElevated: '#1B2420',
  surfaceSubtle: '#1F2925',
  surfaceMutedRejected: '#161C19',
  borderSubtle: '#2C3933',
  borderStrong: '#52665C',
  textPrimary: '#F2F5F3', // 16.2:1 on surface
  textSecondary: '#C5D0C9', // 10.4:1 on surface
  textMuted: '#9BA9A0', // 6.3:1 on surface (exceeds WCAG AA 4.5:1)
  brandPrimary: '#2DD4A8', // High-contrast mint on dark — 10.5:1 with #08221B text
  brandPrimaryHover: '#5EEAD4',
  brandContrastText: '#062019',
  legalPassBg: '#0E2E24',
  legalPassText: '#86EFAC', // 8.8:1 on legalPassBg
  legalPassBorder: '#1E5E4A',
  ruleWarnBg: '#2C1414',
  ruleWarnText: '#FCA5A5', // 7.8:1 on ruleWarnBg
  ruleWarnBorder: '#6E2828',
  amberAlertBg: '#2B1F0E',
  amberAlertText: '#FCD34D', // 8.9:1 on amberAlertBg
  amberAlertBorder: '#6B4C1B',
  focusRing: '#60A5FA',
};

export function createCoverCallTheme(mode: 'light' | 'dark'): Theme {
  const t = mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  return createTheme({
    spacing: 8, // Strict 8px spacing grid (§11.6)
    palette: {
      mode,
      background: {
        default: t.canvas,
        paper: t.surface,
      },
      text: {
        primary: t.textPrimary,
        secondary: t.textSecondary,
      },
      primary: {
        main: t.brandPrimary,
        dark: t.brandPrimaryHover,
        contrastText: t.brandContrastText,
      },
      error: {
        main: t.ruleWarnText,
      },
      warning: {
        main: t.amberAlertText,
      },
      success: {
        main: t.legalPassText,
      },
      divider: t.borderSubtle,
    },
    shape: {
      borderRadius: 12,
    },
    typography: {
      fontFamily: '"Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      h1: {
        fontSize: '1.5rem', // 24px
        fontWeight: 700,
        lineHeight: 1.25,
        letterSpacing: '-0.02em',
      },
      h2: {
        fontSize: '1.125rem', // 18px
        fontWeight: 700,
        lineHeight: 1.3,
        letterSpacing: '-0.01em',
      },
      h3: {
        fontSize: '1rem', // 16px
        fontWeight: 600,
        lineHeight: 1.35,
      },
      body1: {
        fontSize: '0.9375rem', // 15px
        fontWeight: 400,
        lineHeight: 1.55,
      },
      body2: {
        fontSize: '0.84375rem', // 13.5px
        fontWeight: 400,
        lineHeight: 1.5,
      },
      caption: {
        fontSize: '0.78125rem', // 12.5px
        fontWeight: 500,
        lineHeight: 1.4,
      },
      button: {
        textTransform: 'none',
        fontWeight: 600,
        fontSize: '0.9rem',
        letterSpacing: '0',
      },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          '*, *::before, *::after': {
            boxSizing: 'border-box',
          },
          html: {
            WebkitFontSmoothing: 'antialiased',
            MozOsxFontSmoothing: 'grayscale',
          },
          body: {
            backgroundColor: t.canvas,
            color: t.textPrimary,
            margin: 0,
            padding: 0,
            overflowX: 'hidden',
          },
          '.mono-tabular': {
            fontFamily: '"IBM Plex Mono", monospace',
            fontVariantNumeric: 'tabular-nums',
          },
          // Visible focus ring for keyboard navigation (§11.7)
          '*:focus-visible': {
            outline: `3px solid ${t.focusRing} !important`,
            outlineOffset: '2px !important',
          },
          // Respect prefers-reduced-motion (§11.6)
          '@media (prefers-reduced-motion: reduce)': {
            '*, *::before, *::after': {
              animationDuration: '0.01ms !important',
              animationIterationCount: '1 !important',
              transitionDuration: '0.01ms !important',
              scrollBehavior: 'auto !important',
            },
          },
        },
      },
      MuiButtonBase: {
        defaultProps: {
          disableRipple: true, // Clean, fast tactile press instead of default MUI ripple
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            minHeight: 48, // Release-blocking 48x48px touch target (§11.7)
            minWidth: 48,
            padding: '10px 16px',
            borderRadius: 10,
            boxShadow: 'none',
            whiteSpace: 'nowrap',
            transition: 'transform 150ms cubic-bezier(0.16, 1, 0.3, 1), background-color 150ms ease, border-color 150ms ease',
            '&:hover': {
              boxShadow: 'none',
            },
            '&:active': {
              transform: 'scale(0.99)',
            },
          },
          outlined: {
            borderWidth: '1.5px',
            borderColor: t.borderStrong,
            color: t.textPrimary,
            '&:hover': {
              borderWidth: '1.5px',
              backgroundColor: t.surfaceSubtle,
              borderColor: t.textPrimary,
            },
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            minWidth: 48,
            minHeight: 48,
            borderRadius: 10,
          },
        },
      },
      MuiPaper: {
        defaultProps: {
          elevation: 0,
        },
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            border: `1px solid ${t.borderSubtle}`,
            borderRadius: 12,
          },
        },
      },
      MuiLink: {
        styleOverrides: {
          root: {
            color: t.brandPrimary,
            fontWeight: 600,
            textDecorationThickness: '1.5px',
            textUnderlineOffset: '3px',
            '&:hover': {
              color: t.brandPrimaryHover,
            },
          },
        },
      },
    },
  });
}
