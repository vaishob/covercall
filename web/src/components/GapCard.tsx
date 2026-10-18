import React, { useEffect, useState } from 'react';
import { Box, Paper, Typography, useTheme } from '@mui/material';
import StorefrontOutlinedIcon from '@mui/icons-material/StorefrontOutlined';
import AccessTimeOutlinedIcon from '@mui/icons-material/AccessTimeOutlined';
import HourglassBottomOutlinedIcon from '@mui/icons-material/HourglassBottomOutlined';
import VerifiedOutlinedIcon from '@mui/icons-material/VerifiedOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import { GapRecord } from '../mocks/state';
import {
  formatCurrencySGD,
  formatTime12h,
  getThrottledAriaCountdown,
} from '../utils/formatters';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { MockDataBadge } from './MockDataBadge';

interface GapCardProps {
  gap: GapRecord;
  isMockMode?: boolean;
  onInspectTrace: () => void;
}

export const GapCard: React.FC<GapCardProps> = ({
  gap,
  isMockMode = true,
  onInspectTrace,
}) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  const [secondsLeft, setSecondsLeft] = useState(gap.must_fill_by_minutes * 60);

  useEffect(() => {
    setSecondsLeft(gap.must_fill_by_minutes * 60);
  }, [gap.id, gap.must_fill_by_minutes]);

  useEffect(() => {
    if (gap.state === 'FILLED' || gap.state === 'RESOLVED') return;
    const timer = window.setInterval(() => {
      setSecondsLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [gap.state]);

  const mins = Math.floor(secondsLeft / 60);
  const secs = String(secondsLeft % 60).padStart(2, '0');
  const throttledAriaMessage = getThrottledAriaCountdown(secondsLeft);

  const isUrgent = mins < 18 && gap.state !== 'FILLED';
  const isFilled = gap.state === 'FILLED' || gap.state === 'RESOLVED';

  return (
    <Paper
      component="section"
      aria-label={`Shift Gap at ${gap.outletName}`}
      sx={{
        p: 2,
        backgroundColor: tokens.surface,
      }}
    >
      {/* Header Row: Outlet & Station + State Label */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 1.5,
          mb: 2,
        }}
      >
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap', mb: 0.5 }}>
            <StorefrontOutlinedIcon
              sx={{ fontSize: 18, color: tokens.brandPrimary }}
              aria-hidden="true"
            />
            <Typography
              variant="caption"
              className="mono-tabular"
              sx={{ color: tokens.textSecondary, fontWeight: 600 }}
            >
              Scenario: {gap.scenarioId} · Reported {formatTime12h(gap.now)} · v{gap.version}
            </Typography>
            <MockDataBadge isMockMode={isMockMode || gap.is_mock} />
          </Box>
          <Typography variant="h1" component="h2" sx={{ color: tokens.textPrimary }}>
            {gap.outletName} · {gap.stationDisplay}
          </Typography>
          <Typography variant="body2" sx={{ color: tokens.textSecondary, mt: 0.25 }}>
            Absent: <strong>{gap.absent_staff_name}</strong>
          </Typography>
        </Box>

        {/* Workflow State Status Box (Icon + Text, never color alone) */}
        <Box
          sx={{
            px: 1.5,
            py: 0.75,
            borderRadius: 2,
            backgroundColor: isFilled
              ? tokens.legalPassBg
              : gap.state === 'ESCALATED' || gap.state === 'HELD'
                ? tokens.ruleWarnBg
                : tokens.amberAlertBg,
            color: isFilled
              ? tokens.legalPassText
              : gap.state === 'ESCALATED' || gap.state === 'HELD'
                ? tokens.ruleWarnText
                : tokens.amberAlertText,
            border: `1px solid ${
              isFilled
                ? tokens.legalPassBorder
                : gap.state === 'ESCALATED' || gap.state === 'HELD'
                  ? tokens.ruleWarnBorder
                  : tokens.amberAlertBorder
            }`,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0.75,
          }}
        >
          {isFilled ? (
            <VerifiedOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />
          ) : (
            <WarningAmberOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />
          )}
          <Typography
            component="span"
            className="mono-tabular"
            sx={{ fontSize: '0.78rem', fontWeight: 700 }}
          >
            State: {gap.state}
          </Typography>
        </Box>
      </Box>

      {/* Metrics Row: Shift Start/End + Countdown to Must-Fill-By + Overtime Saved */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' },
          gap: 1.5,
          p: 1.5,
          borderRadius: 2,
          backgroundColor: tokens.surfaceSubtle,
          border: `1px solid ${tokens.borderSubtle}`,
        }}
      >
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.25 }}>
            <AccessTimeOutlinedIcon
              sx={{ fontSize: 15, color: tokens.textSecondary }}
              aria-hidden="true"
            />
            <Typography variant="caption" sx={{ color: tokens.textSecondary }}>
              Shift Window (8.0h)
            </Typography>
          </Box>
          <Typography
            className="mono-tabular"
            sx={{ fontSize: '1.05rem', fontWeight: 700, color: tokens.textPrimary }}
          >
            {formatTime12h(gap.start)} – {formatTime12h(gap.end)}
          </Typography>
          <Typography variant="caption" sx={{ color: tokens.textMuted, display: 'block' }}>
            Includes 45m meal break (SG-EA4-BREAKS)
          </Typography>
        </Box>

        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.25 }}>
            <HourglassBottomOutlinedIcon
              sx={{
                fontSize: 15,
                color: isUrgent ? tokens.ruleWarnText : tokens.amberAlertText,
              }}
              aria-hidden="true"
            />
            <Typography variant="caption" sx={{ color: tokens.textSecondary }}>
              Must-Fill-By Deadline
            </Typography>
          </Box>
          <Typography
            className="mono-tabular"
            sx={{
              fontSize: '1.05rem',
              fontWeight: 700,
              color: isFilled
                ? tokens.legalPassText
                : isUrgent
                  ? tokens.ruleWarnText
                  : tokens.amberAlertText,
            }}
          >
            {isFilled
              ? 'Filled on time'
              : `${formatTime12h(gap.must_fill_by)} · ${mins}m ${secs}s left`}
          </Typography>
          <Box sx={{ mt: 0.25 }}>
            <MockDataBadge isMockMode={isMockMode || gap.is_mock} />
          </Box>
          <Box
            aria-live="polite"
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
            {throttledAriaMessage}
          </Box>
        </Box>

        <Box>
          <Typography variant="caption" sx={{ color: tokens.textSecondary, display: 'block', mb: 0.25 }}>
            Overtime Cost Avoided vs Baseline
          </Typography>
          <Typography
            className="mono-tabular"
            sx={{ fontSize: '1.05rem', fontWeight: 700, color: tokens.legalPassText }}
          >
            Saves {formatCurrencySGD(gap.cost_saved_sgd)}
          </Typography>
          <Box sx={{ mt: 0.25, mb: 0.25 }}>
            <MockDataBadge isMockMode={isMockMode || gap.is_mock} />
          </Box>
          <Typography
            component="button"
            type="button"
            onClick={onInspectTrace}
            sx={{
              background: 'none',
              border: 'none',
              p: 0,
              minHeight: 48,
              display: 'inline-flex',
              alignItems: 'center',
              cursor: 'pointer',
              textAlign: 'left',
              color: tokens.brandPrimary,
              fontSize: '0.76rem',
              fontWeight: 600,
              textDecoration: 'underline',
            }}
          >
            Trace: {gap.workflow_execution_id} →
          </Typography>
        </Box>
      </Box>
    </Paper>
  );
};
