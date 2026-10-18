import React from 'react';
import { Box, Button, Paper, Typography, useTheme } from '@mui/material';
import StorefrontOutlinedIcon from '@mui/icons-material/StorefrontOutlined';
import AccessTimeOutlinedIcon from '@mui/icons-material/AccessTimeOutlined';
import HourglassBottomOutlinedIcon from '@mui/icons-material/HourglassBottomOutlined';
import VerifiedOutlinedIcon from '@mui/icons-material/VerifiedOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import type { GapView } from '../data/viewModel';
import { centsToSgd } from '../data/viewModel';
import { formatTime12h, getThrottledAriaCountdown } from '../utils/formatters';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { ReplayBadge } from './ReplayBadge';

interface GapCardProps {
  gap: GapView;
  naiveName: string | null;
  isReplay: boolean;
  canAct: boolean;
  onInspectTrace: () => void;
  onCancel: () => void;
}

/** The gap (§11.3 item 3). The escalation countdown target is the server's locked t_esc. */
export const GapCard: React.FC<GapCardProps> = ({ gap, naiveName, isReplay, canAct, onInspectTrace, onCancel }) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;
  const done = gap.state === 'FILLED' || gap.state === 'RESOLVED';
  const warn = gap.state === 'ESCALATED' || gap.state === 'HELD' || gap.state === 'CANCELLED';
  const secs = gap.secondsToEscalation;
  const tone = done
    ? { bg: tokens.legalPassBg, fg: tokens.legalPassText, bd: tokens.legalPassBorder }
    : warn
      ? { bg: tokens.ruleWarnBg, fg: tokens.ruleWarnText, bd: tokens.ruleWarnBorder }
      : { bg: tokens.amberAlertBg, fg: tokens.amberAlertText, bd: tokens.amberAlertBorder };

  return (
    <Paper component="section" aria-label={`Shift gap at ${gap.outletName}`} sx={{ p: 2, backgroundColor: tokens.surface }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1.5, mb: 2 }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap', mb: 0.5 }}>
            <StorefrontOutlinedIcon sx={{ fontSize: 18, color: tokens.brandPrimary }} aria-hidden="true" />
            <Typography variant="caption" className="mono-tabular" sx={{ color: tokens.textSecondary, fontWeight: 600 }}>
              {gap.scenarioId ? `Scenario ${gap.scenarioId} · ` : ''}Reported {formatTime12h(gap.reportedAt)} · {gap.gapId} · v{gap.version}
            </Typography>
            <ReplayBadge show={isReplay} />
          </Box>
          <Typography variant="h1" component="h2">
            {gap.outletName} · {gap.station}
          </Typography>
          <Typography variant="body2" sx={{ color: tokens.textSecondary, mt: 0.25 }}>
            Absent: <strong>{gap.absentName}</strong>
          </Typography>
        </Box>
        <Box
          data-testid="gap-state"
          sx={{ px: 1.5, py: 0.75, borderRadius: 2, backgroundColor: tone.bg, color: tone.fg, border: `1px solid ${tone.bd}`, display: 'inline-flex', alignItems: 'center', gap: 0.75 }}
        >
          {done ? <VerifiedOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" /> : <WarningAmberOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />}
          <Typography component="span" className="mono-tabular" sx={{ fontSize: '0.78rem', fontWeight: 700 }}>
            State: {gap.state}
            {gap.outcomeLabel ? ` · ${gap.outcomeLabel}` : ''}
          </Typography>
        </Box>
      </Box>

      <Box
        sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' }, gap: 1.5, p: 1.5, borderRadius: 2, backgroundColor: tokens.surfaceSubtle, border: `1px solid ${tokens.borderSubtle}` }}
      >
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.25 }}>
            <AccessTimeOutlinedIcon sx={{ fontSize: 15, color: tokens.textSecondary }} aria-hidden="true" />
            <Typography variant="caption" sx={{ color: tokens.textSecondary }}>Shift</Typography>
          </Box>
          <Typography className="mono-tabular" sx={{ fontSize: '1.05rem', fontWeight: 700 }}>
            {formatTime12h(gap.start)} – {formatTime12h(gap.end)}
          </Typography>
        </Box>

        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.25 }}>
            <HourglassBottomOutlinedIcon sx={{ fontSize: 15, color: tone.fg }} aria-hidden="true" />
            <Typography variant="caption" sx={{ color: tokens.textSecondary }}>Escalates to you at</Typography>
          </Box>
          <Typography className="mono-tabular" data-testid="escalation-at" sx={{ fontSize: '1.05rem', fontWeight: 700 }}>
            {gap.escalationAt
              ? `${formatTime12h(gap.escalationAt)}${secs !== null ? ` · ${Math.floor(secs / 60)}m ${String(secs % 60).padStart(2, '0')}s left` : ''}`
              : 'Set when you approve the plan'}
          </Typography>
          {secs !== null && (
            <Box component="span" aria-live="polite" sx={{ position: 'absolute', width: '1px', height: '1px', overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>
              {getThrottledAriaCountdown(secs)}
            </Box>
          )}
          {gap.timeScale !== 1 && (
            <Typography variant="caption" sx={{ color: tokens.textMuted, display: 'block' }}>
              Simulated time (demo compression ×{gap.timeScale})
            </Typography>
          )}
        </Box>

        <Box>
          <Typography variant="caption" sx={{ color: tokens.textSecondary, display: 'block', mb: 0.25 }}>
            Overtime vs the usual first pick{naiveName ? ` (${naiveName})` : ''}
          </Typography>
          <Typography className="mono-tabular" sx={{ fontSize: '1.05rem', fontWeight: 700 }}>
            {gap.costSavedCents === null ? 'Known once filled' : `${centsToSgd(gap.costSavedCents)} less`}
          </Typography>
          <Typography variant="caption" sx={{ color: tokens.textMuted, display: 'block' }}>
            Synthetic wages; not a claim about real money.
          </Typography>
        </Box>
      </Box>

      {gap.summary && (
        <Typography role="status" sx={{ mt: 1.5, fontWeight: 600 }}>
          {gap.summary}
        </Typography>
      )}

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1.5 }}>
        <Button variant="outlined" onClick={onInspectTrace} sx={{ minHeight: 48 }}>
          Trace replay (event chain)
        </Button>
        {!gap.isTerminal && (
          <Button variant="outlined" color="error" onClick={onCancel} disabled={!canAct} sx={{ minHeight: 48 }}>
            Cancel gap
          </Button>
        )}
      </Box>
    </Paper>
  );
};
