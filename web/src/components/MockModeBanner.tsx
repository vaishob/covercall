import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';

interface MockModeBannerProps {
  isMockMode: boolean;
  sourceName: string;
  apiBaseUrl: string | null;
}

export const MockModeBanner: React.FC<MockModeBannerProps> = ({
  isMockMode,
  sourceName,
  apiBaseUrl,
}) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  if (!isMockMode) return null;

  return (
    <Box
      role="status"
      aria-label="Mock mode active notice"
      data-testid="mock-mode-banner"
      sx={{
        backgroundColor: tokens.amberAlertBg,
        color: tokens.amberAlertText,
        borderBottom: `1.5px solid ${tokens.amberAlertBorder}`,
        px: 1.5,
        py: 0.75,
      }}
    >
      <Box
        sx={{
          maxWidth: 1080,
          mx: 'auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <InfoOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />
          <Typography sx={{ fontSize: '0.78rem', fontWeight: 700 }}>
            Mock mode active ({sourceName}) — VITE_API_BASE_URL is unset ({apiBaseUrl ?? 'none'}).
            All displayed costs, travel times, OT hours, and rankings are mock fixtures, not computed by the backend solver.
          </Typography>
        </Box>
      </Box>
    </Box>
  );
};
