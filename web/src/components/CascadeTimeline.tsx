import React from 'react';
import { Box, Button, Paper, Typography, useTheme } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import SwapCallsOutlinedIcon from '@mui/icons-material/SwapCallsOutlined';
import TimerOffOutlinedIcon from '@mui/icons-material/TimerOffOutlined';
import ShieldOutlinedIcon from '@mui/icons-material/ShieldOutlined';
import FastForwardOutlinedIcon from '@mui/icons-material/FastForwardOutlined';
import { CascadeOfferItem } from '../mocks/state';
import { formatTime12h } from '../utils/formatters';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { MockDataBadge } from './MockDataBadge';

interface CascadeTimelineProps {
  offers: CascadeOfferItem[];
  guardImpl?: string | null;
  isMockMode?: boolean;
  quarantinedMessage?: {
    id: string;
    staff_id: string;
    staff_name: string;
    guard_labels: string[];
    redacted_text: string;
    action_taken: string;
  };
  activeStepCount: number;
  onAdvanceCascadeStep: () => void;
}

export const CascadeTimeline: React.FC<CascadeTimelineProps> = ({
  offers,
  guardImpl = null,
  isMockMode = true,
  quarantinedMessage,
  activeStepCount,
  onAdvanceCascadeStep,
}) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  const visibleOffers = offers.slice(0, activeStepCount);
  const guardDisplayLabel = guardImpl ? `Guard (${guardImpl})` : 'Guard (stub)';

  const getStatusMeta = (status: CascadeOfferItem['status']) => {
    switch (status) {
      case 'accepted':
        return {
          icon: <CheckCircleOutlineIcon sx={{ fontSize: 16 }} aria-hidden="true" />,
          label: 'Accepted',
          bg: tokens.legalPassBg,
          color: tokens.legalPassText,
          border: tokens.legalPassBorder,
        };
      case 'counter_offered':
        return {
          icon: <SwapCallsOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />,
          label: 'Counter-Offer',
          bg: tokens.amberAlertBg,
          color: tokens.amberAlertText,
          border: tokens.amberAlertBorder,
        };
      case 'declined':
        return {
          icon: <CancelOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />,
          label: 'Declined',
          bg: tokens.surfaceSubtle,
          color: tokens.textSecondary,
          border: tokens.borderStrong,
        };
      case 'timed_out':
        return {
          icon: <TimerOffOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />,
          label: 'Reply Window Timed Out',
          bg: tokens.surfaceSubtle,
          color: tokens.textSecondary,
          border: tokens.borderStrong,
        };
      default:
        return {
          icon: <SwapCallsOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />,
          label: 'Awaiting Callback',
          bg: tokens.amberAlertBg,
          color: tokens.amberAlertText,
          border: tokens.amberAlertBorder,
        };
    }
  };

  return (
    <Paper
      component="section"
      aria-label="Outreach Cascade Timeline"
      sx={{
        p: 2,
        backgroundColor: tokens.surface,
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
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Typography variant="h2" component="h2">
              Outreach Cascade Timeline
            </Typography>
            <MockDataBadge isMockMode={isMockMode} />
          </Box>
          <Typography variant="body2" sx={{ color: tokens.textSecondary }}>
            Offer sequence, reply window countdown, and inbound reply status ({guardDisplayLabel})
          </Typography>
        </Box>

        <Button
          variant="outlined"
          size="small"
          onClick={onAdvanceCascadeStep}
          aria-label="Step through outreach cascade replies"
          sx={{ minHeight: 48, fontSize: '0.8rem' }}
        >
          <FastForwardOutlinedIcon sx={{ fontSize: 18, mr: 0.5 }} aria-hidden="true" />
          {activeStepCount < offers.length
            ? `Reveal Next Reply (${activeStepCount}/${offers.length})`
            : 'Replay Cascade Step-by-Step'}
        </Button>
      </Box>

      {/* Quarantined Adversarial Prompt Injection Card (relabeled to Guard (stub) / Flagged for review when guard_impl is unset) */}
      {quarantinedMessage && (
        <Box
          role="alert"
          sx={{
            p: 1.5,
            mb: 2,
            borderRadius: 2,
            backgroundColor: tokens.ruleWarnBg,
            color: tokens.ruleWarnText,
            border: `1.5px solid ${tokens.ruleWarnBorder}`,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap', mb: 0.5 }}>
            <ShieldOutlinedIcon sx={{ fontSize: 18 }} aria-hidden="true" />
            <Typography sx={{ fontSize: '0.85rem', fontWeight: 700 }}>
              Flagged for review ({guardDisplayLabel}) · Labels: [
              {quarantinedMessage.guard_labels.join(', ')}]
            </Typography>
            <MockDataBadge isMockMode={isMockMode} />
          </Box>
          <Typography
            className="mono-tabular"
            sx={{
              fontSize: '0.82rem',
              p: 1,
              my: 0.75,
              borderRadius: 1,
              backgroundColor: tokens.surface,
              color: tokens.textPrimary,
              border: `1px solid ${tokens.ruleWarnBorder}`,
            }}
          >
            From {quarantinedMessage.staff_name}: &ldquo;{quarantinedMessage.redacted_text}&rdquo;
          </Typography>
          <Typography sx={{ fontSize: '0.78rem' }}>{quarantinedMessage.action_taken}</Typography>
        </Box>
      )}

      {/* Cascade Offer Steps */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {visibleOffers.map((offer) => {
          const meta = getStatusMeta(offer.status);
          const windowMin = Math.round(offer.window_s / 60);

          return (
            <Box
              key={offer.offer_id}
              sx={{
                p: 1.5,
                borderRadius: 2,
                backgroundColor: tokens.surfaceSubtle,
                border: `1px solid ${tokens.borderSubtle}`,
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 1,
                  mb: 0.75,
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography
                    component="span"
                    className="mono-tabular"
                    sx={{ fontSize: '0.78rem', fontWeight: 700, color: tokens.textSecondary }}
                  >
                    Offer #{offer.seq}
                  </Typography>
                  <Typography component="span" sx={{ fontSize: '0.9rem', fontWeight: 700 }}>
                    {offer.staff_name}
                  </Typography>
                </Box>

                <Box
                  sx={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 0.5,
                    px: 1,
                    py: 0.35,
                    borderRadius: 1.5,
                    backgroundColor: meta.bg,
                    color: meta.color,
                    border: `1px solid ${meta.border}`,
                  }}
                >
                  {meta.icon}
                  <Typography component="span" sx={{ fontSize: '0.74rem', fontWeight: 700 }}>
                    {meta.label}
                  </Typography>
                </Box>
              </Box>

              {/* Metadata line: sent time, reply window, guard status */}
              <Typography
                variant="caption"
                className="mono-tabular"
                sx={{ display: 'block', color: tokens.textMuted, mb: 0.75 }}
              >
                Sent {formatTime12h(offer.sent_at_iso)} via{' '}
                {offer.channel === 'telegram' ? 'Telegram' : 'Persona Sim'} · Reply window:{' '}
                {windowMin}m00s · {offer.guard_status_label}
              </Typography>

              {/* Staff Reply Bubble */}
              {offer.reply_raw_text && (
                <Box
                  sx={{
                    p: 1.25,
                    borderRadius: 1.5,
                    backgroundColor: tokens.surface,
                    border: `1px solid ${tokens.borderSubtle}`,
                  }}
                >
                  <Typography sx={{ fontSize: '0.88rem', fontWeight: 600 }}>
                    &ldquo;{offer.reply_raw_text}&rdquo;
                  </Typography>
                  {offer.parsed_reply && (
                    <Typography
                      variant="caption"
                      className="mono-tabular"
                      sx={{ display: 'block', color: tokens.textSecondary, mt: 0.5 }}
                    >
                      Parsed reply (mock) → intent: {offer.parsed_reply.intent}
                      {offer.parsed_reply.counter_window
                        ? ` (${offer.parsed_reply.counter_window.start}–${offer.parsed_reply.counter_window.end})`
                        : ''}{' '}
                      · reason: {offer.parsed_reply.reason_category} · conf:{' '}
                      {offer.parsed_reply.confidence.toFixed(2)} · tags: [
                      {offer.parsed_reply.language_tags.join(', ')}]
                    </Typography>
                  )}
                </Box>
              )}
            </Box>
          );
        })}
      </Box>
    </Paper>
  );
};
