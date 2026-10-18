import React from 'react';
import { Box, Paper, Typography, useTheme } from '@mui/material';
import SubtitlesOutlinedIcon from '@mui/icons-material/SubtitlesOutlined';
import { CaptionExchange, VoiceState } from '../mocks/state';
import { formatTime12h } from '../utils/formatters';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { MockDataBadge } from './MockDataBadge';

interface CaptionsPanelProps {
  captions: CaptionExchange[];
  voiceState: VoiceState;
  statusAnnouncement: string;
  isMockMode?: boolean;
}

export const CaptionsPanel: React.FC<CaptionsPanelProps> = ({
  captions,
  voiceState,
  statusAnnouncement,
  isMockMode = true,
}) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  return (
    <Paper
      component="section"
      aria-label="Live Voice Captions"
      sx={{
        p: 2,
        backgroundColor: tokens.surface,
        borderColor: tokens.borderStrong,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 1,
          mb: 1.5,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SubtitlesOutlinedIcon
            fontSize="small"
            sx={{ color: tokens.textSecondary }}
            aria-hidden="true"
          />
          <Typography
            variant="h3"
            component="h2"
            sx={{ fontSize: '0.9rem', fontWeight: 700, color: tokens.textPrimary }}
          >
            Live Captions
          </Typography>
          <MockDataBadge isMockMode={isMockMode} />
        </Box>
        <Typography
          variant="caption"
          className="mono-tabular"
          sx={{ color: tokens.textMuted }}
        >
          State: {voiceState} · Redacted transcript
        </Typography>
      </Box>

      {/* Polite aria-live region for voice exchanges and throttled state transitions (§7.2, §11.7) */}
      <Box
        aria-live="polite"
        aria-atomic="false"
        role="log"
        aria-label="Recent voice transcript exchanges"
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 1.5,
        }}
      >
        {captions.map((exchange) => {
          const isLead = exchange.speaker === 'Lead';
          const isGuard = exchange.speaker === 'Guard (stub)';

          return (
            <Box
              key={exchange.id}
              sx={{
                p: 1.5,
                borderRadius: 2,
                backgroundColor: isGuard
                  ? tokens.ruleWarnBg
                  : exchange.highlight
                    ? tokens.legalPassBg
                    : tokens.surfaceSubtle,
                border: `1px solid ${
                  isGuard
                    ? tokens.ruleWarnBorder
                    : exchange.highlight
                      ? tokens.legalPassBorder
                      : tokens.borderSubtle
                }`,
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'baseline',
                  justifyContent: 'space-between',
                  mb: 0.5,
                  gap: 1,
                }}
              >
                <Typography
                  component="span"
                  sx={{
                    fontSize: '0.78rem',
                    fontWeight: 700,
                    color: isGuard
                      ? tokens.ruleWarnText
                      : exchange.highlight
                        ? tokens.legalPassText
                        : tokens.textSecondary,
                  }}
                >
                  {isLead
                    ? 'You (Shift Lead)'
                    : isGuard
                      ? 'Guard (stub) · Flagged for review'
                      : 'CoverCall'}
                </Typography>
                <Typography
                  component="span"
                  className="mono-tabular"
                  sx={{ fontSize: '0.75rem', color: tokens.textMuted }}
                >
                  {formatTime12h(exchange.timestampIso)}
                </Typography>
              </Box>
              <Typography
                sx={{
                  fontSize: '1.0625rem',
                  fontWeight: exchange.highlight ? 600 : 500,
                  lineHeight: 1.45,
                  color: isGuard
                    ? tokens.ruleWarnText
                    : exchange.highlight
                      ? tokens.legalPassText
                      : tokens.textPrimary,
                }}
              >
                {exchange.text}
              </Typography>
            </Box>
          );
        })}

        {statusAnnouncement && (
          <Box
            sx={{
              position: 'absolute',
              left: 0,
              top: 0,
              width: '1px',
              height: '1px',
              padding: 0,
              margin: '-1px',
              overflow: 'hidden',
              clip: 'rect(0, 0, 0, 0)',
              whiteSpace: 'nowrap',
              border: 0,
            }}
          >
            {statusAnnouncement}
          </Box>
        )}
      </Box>
    </Paper>
  );
};
