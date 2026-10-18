import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';

interface ReplayBannerProps {
  show: boolean;
}

export const ReplayBanner: React.FC<ReplayBannerProps> = ({ show }) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;
  if (!show) return null;
  return (
    <Box
      role="status"
      data-testid="replay-banner"
      sx={{
        backgroundColor: tokens.amberAlertBg,
        color: tokens.amberAlertText,
        borderBottom: `1.5px solid ${tokens.amberAlertBorder}`,
        px: 1.5,
        py: 0.75,
      }}
    >
      <Box sx={{ maxWidth: 1080, mx: 'auto', display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <InfoOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />
        <Typography sx={{ fontSize: '0.78rem', fontWeight: 700 }}>
          Recorded replay, not live: VITE_API_BASE_URL is unset, so this page plays back real API
          responses recorded from a local run of the cascade. Buttons that change state are disabled.
        </Typography>
      </Box>
    </Box>
  );
};
