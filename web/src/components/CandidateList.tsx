import React from 'react';
import { Box, Button, Paper, Typography, useTheme } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import DirectionsTransitOutlinedIcon from '@mui/icons-material/DirectionsTransitOutlined';
import SwapHorizOutlinedIcon from '@mui/icons-material/SwapHorizOutlined';
import TelegramIcon from '@mui/icons-material/Telegram';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import { FeasibleCandidate, RejectedCandidate } from '../mocks/state';
import { formatCurrencySGD, formatTime12h } from '../utils/formatters';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { RuleWarningCard } from './RuleWarningCard';
import { MockDataBadge } from './MockDataBadge';

interface CandidateListProps {
  candidates: FeasibleCandidate[];
  rejectedCandidates: RejectedCandidate[];
  selectedRank: number;
  isMockMode?: boolean;
  onSelectCandidate: (rank: number) => void;
  onToggleChannel: (staffId: string) => void;
}

export const CandidateList: React.FC<CandidateListProps> = ({
  candidates,
  rejectedCandidates,
  selectedRank,
  isMockMode = true,
  onSelectCandidate,
  onToggleChannel,
}) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  return (
    <Box
      component="section"
      aria-label="Ranked Replacement Candidates and Rule Warnings"
      sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
    >
      {/* Section Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 1,
        }}
      >
        <Typography variant="h2" component="h2">
          Ranked Legal Candidates (Top {candidates.length})
        </Typography>
        <MockDataBadge isMockMode={isMockMode} />
      </Box>

      {/* Up to 3 Ranked Feasible Candidate Cards (§11.3) */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {candidates.map((cand) => {
          const isSelected = cand.rank === selectedRank;
          const showMock = isMockMode || cand.is_mock;
          return (
            <Paper
              key={cand.staff_id}
              component="article"
              aria-label={`Rank ${cand.rank}: ${cand.display_name}, arrives ${formatTime12h(
                cand.arrival_iso
              )}, cost ${formatCurrencySGD(cand.incremental_cost_sgd)}, saves ${formatCurrencySGD(
                cand.saves_vs_overtime_sgd
              )}`}
              sx={{
                p: 2,
                backgroundColor: tokens.surface,
                borderWidth: isSelected ? 2 : 1,
                borderColor: isSelected ? tokens.brandPrimary : tokens.borderSubtle,
              }}
            >
              {/* Top Row: Rank + Name + Outlet Borrow Indicator + Cost & Savings */}
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 1.5,
                  mb: 1.25,
                }}
              >
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                    <Typography
                      component="span"
                      className="mono-tabular"
                      sx={{
                        fontSize: '0.8rem',
                        fontWeight: 700,
                        color: tokens.brandPrimary,
                      }}
                    >
                      #{cand.rank} {cand.rank === 1 ? '· Top Pick' : ''}
                    </Typography>
                    <Typography variant="h3" component="h3" sx={{ fontWeight: 700 }}>
                      {cand.display_name}
                    </Typography>
                    <Typography
                      variant="caption"
                      className="mono-tabular"
                      sx={{ color: tokens.textMuted }}
                    >
                      ({cand.staff_id})
                    </Typography>
                  </Box>

                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      flexWrap: 'wrap',
                      mt: 0.5,
                      color: tokens.textSecondary,
                      fontSize: '0.82rem',
                    }}
                  >
                    {cand.is_cross_outlet_borrow ? (
                      <Box
                        component="span"
                        sx={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 0.5,
                          fontWeight: 600,
                          color: tokens.brandPrimary,
                        }}
                      >
                        <SwapHorizOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />
                        <span>Cross-outlet borrow from {cand.home_outlet}</span>
                      </Box>
                    ) : (
                      <span>Home outlet: {cand.home_outlet}</span>
                    )}
                    <span aria-hidden="true">·</span>
                    <span>
                      {cand.contract_type === 'full_time' ? 'Full-time' : 'Part-time (Student)'}
                    </span>
                  </Box>
                </Box>

                {/* Cost & Overtime Savings Box with MockDataBadge */}
                <Box sx={{ textAlign: { xs: 'left', sm: 'right' } }}>
                  <Typography
                    className="mono-tabular"
                    sx={{
                      fontSize: '1.05rem',
                      fontWeight: 700,
                      color: tokens.legalPassText,
                    }}
                  >
                    Saves {formatCurrencySGD(cand.saves_vs_overtime_sgd)} vs overtime
                  </Typography>
                  <Typography
                    variant="caption"
                    className="mono-tabular"
                    sx={{ color: tokens.textSecondary, display: 'block', mb: 0.4 }}
                  >
                    Shift cost: {formatCurrencySGD(cand.incremental_cost_sgd)} · OT used:{' '}
                    {cand.ot_hours_used}/{cand.ot_hours_max}h
                  </Typography>
                  <MockDataBadge isMockMode={showMock} />
                </Box>
              </Box>

              {/* Middle Row: Arrival Time & Travel Route with MockDataBadge */}
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 1,
                  p: 1.25,
                  mb: 1.25,
                  borderRadius: 1.5,
                  backgroundColor: tokens.surfaceSubtle,
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <DirectionsTransitOutlinedIcon
                    sx={{ fontSize: 18, color: tokens.textSecondary }}
                    aria-hidden="true"
                  />
                  <Typography sx={{ fontSize: '0.88rem', fontWeight: 600 }}>
                    Arrives{' '}
                    <span className="mono-tabular">{formatTime12h(cand.arrival_iso)}</span> ·{' '}
                    <span className="mono-tabular">{cand.travel_mode}</span>
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                  <Typography
                    variant="caption"
                    className="mono-tabular"
                    sx={{ color: tokens.textMuted }}
                  >
                    {cand.travel_source}
                  </Typography>
                  <MockDataBadge isMockMode={showMock} />
                </Box>
              </Box>

              {/* Plain-English Candidate Summary */}
              <Typography variant="body2" sx={{ color: tokens.textSecondary, mb: 1.25 }}>
                {cand.explanation}
              </Typography>

              {/* Green Check Per Rule (§3 J1 step 3) */}
              <Box
                aria-label={`Rule checks for ${cand.display_name}`}
                sx={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 1,
                  mb: 1.5,
                }}
              >
                {cand.rules_checked.map((rule) => (
                  <Box
                    key={rule.ruleId}
                    title={rule.detail}
                    sx={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 0.5,
                      px: 1,
                      py: 0.35,
                      borderRadius: 1.5,
                      backgroundColor: tokens.legalPassBg,
                      color: tokens.legalPassText,
                      border: `1px solid ${tokens.legalPassBorder}`,
                    }}
                  >
                    <CheckCircleOutlineIcon sx={{ fontSize: 15 }} aria-hidden="true" />
                    <Typography
                      component="span"
                      className="mono-tabular"
                      sx={{ fontSize: '0.73rem', fontWeight: 600 }}
                    >
                      {rule.ruleId} ({rule.shortLabel})
                    </Typography>
                  </Box>
                ))}
              </Box>

              {/* Action Row: Select Primary Plan + Connector Channel Toggle */}
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 1,
                  pt: 1,
                  borderTop: `1px solid ${tokens.borderSubtle}`,
                }}
              >
                <Button
                  variant={isSelected ? 'contained' : 'outlined'}
                  onClick={() => onSelectCandidate(cand.rank)}
                  aria-pressed={isSelected}
                  sx={{ minHeight: 48, fontSize: '0.82rem' }}
                >
                  {isSelected
                    ? `Selected as Lead Plan (#${cand.rank})`
                    : `Select Plan #${cand.rank} (${cand.display_name})`}
                </Button>

                <Button
                  variant="outlined"
                  onClick={() => onToggleChannel(cand.staff_id)}
                  aria-label={`Outreach channel for ${cand.display_name}: ${
                    cand.channel === 'telegram' ? 'Telegram Bot API' : 'Simulated Persona'
                  }. Activate to switch connector mode.`}
                  sx={{
                    minHeight: 48,
                    fontSize: '0.78rem',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 0.75,
                  }}
                >
                  {cand.channel === 'telegram' ? (
                    <TelegramIcon sx={{ fontSize: 17 }} aria-hidden="true" />
                  ) : (
                    <SmartToyOutlinedIcon sx={{ fontSize: 17 }} aria-hidden="true" />
                  )}
                  <span>
                    Channel: {cand.channel === 'telegram' ? 'Telegram' : 'Persona Sim'}
                  </span>
                </Button>
              </Box>
            </Paper>
          );
        })}
      </Box>

      {/* Rejected Candidates with RuleWarning (§11.3 & §11.4) */}
      <Box sx={{ mt: 1 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 1,
            mb: 0.5,
          }}
        >
          <Typography variant="h2" component="h2">
            Excluded Candidates ({rejectedCandidates.length} Blocked)
          </Typography>
          <MockDataBadge isMockMode={isMockMode} />
        </Box>
        <Typography variant="body2" sx={{ color: tokens.textSecondary, mb: 1.5 }}>
          Greyed-out candidates with rule warnings supplied by the policy data layer. A language
          model never decides legality.
        </Typography>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {rejectedCandidates.map((rej) => (
            <RuleWarningCard
              key={`${rej.staff_id}-${rej.rule_id}`}
              rejected={rej}
              isMockMode={isMockMode}
            />
          ))}
        </Box>
      </Box>
    </Box>
  );
};
