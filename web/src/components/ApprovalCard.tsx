import React from 'react';
import { Box, Button, Paper, Typography, useTheme } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import EditNoteOutlinedIcon from '@mui/icons-material/EditNoteOutlined';
import VolumeUpOutlinedIcon from '@mui/icons-material/VolumeUpOutlined';
import { ApprovalRecord, EscalationFallbackOption } from '../mocks/state';
import { formatCurrencySGD } from '../utils/formatters';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';

interface ApprovalCardProps {
  approval: ApprovalRecord;
  escalationOptions?: EscalationFallbackOption[];
  selectedEscalationId?: EscalationFallbackOption['id'];
  onApprove: () => void;
  onRejectOrEdit: () => void;
  onSelectEscalationOption: (option: EscalationFallbackOption) => void;
}

/**
 * §11.3 item 7 & §5.3 Approval Card:
 * Sticky at the bottom, two large buttons, and the exact read-back sentence shown.
 * Compact height to respect mobile sticky surface governance.
 */
export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  approval,
  escalationOptions,
  selectedEscalationId,
  onApprove,
  onRejectOrEdit,
  onSelectEscalationOption,
}) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  const isApproved = approval.status === 'approved';
  const isRejected = approval.status === 'rejected';

  return (
    <Paper
      component="section"
      aria-label="Tier T2 Read-Back Approval Card"
      sx={{
        position: 'sticky',
        bottom: 0,
        zIndex: 25,
        p: 1.5,
        borderRadius: '12px 12px 0 0',
        backgroundColor: tokens.surfaceElevated,
        borderTop: `2px solid ${isApproved ? tokens.legalPassBorder : tokens.brandPrimary}`,
        boxShadow:
          theme.palette.mode === 'light'
            ? '0 -4px 16px rgba(17, 22, 18, 0.08)'
            : '0 -4px 20px rgba(0, 0, 0, 0.45)',
      }}
    >
      {/* Escalation Fallback Picker (Visible in J3 Escalation scenario) */}
      {escalationOptions && escalationOptions.length > 0 && (
        <Box sx={{ mb: 1 }}>
          <Typography
            variant="caption"
            sx={{ fontWeight: 700, color: tokens.ruleWarnText, display: 'block', mb: 0.5 }}
          >
            J3 Escalation Fallbacks (Select by voice or tap):
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 0.75 }}>
            {escalationOptions.map((opt) => {
              const selected = selectedEscalationId === opt.id;
              return (
                <Button
                  key={opt.id}
                  variant={selected ? 'contained' : 'outlined'}
                  onClick={() => onSelectEscalationOption(opt)}
                  aria-pressed={selected}
                  sx={{
                    minHeight: 48,
                    py: 0.5,
                    px: 1,
                    textAlign: 'left',
                    justifyContent: 'flex-start',
                    whiteSpace: 'normal',
                    fontSize: '0.75rem',
                  }}
                >
                  <Typography sx={{ fontSize: '0.75rem', fontWeight: 700 }}>
                    {opt.title} ({formatCurrencySGD(opt.cost_delta_sgd)})
                  </Typography>
                </Button>
              );
            })}
          </Box>
        </Box>
      )}

      {/* Read-back header + exact read-back sentence */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 1,
          mb: 0.5,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <VolumeUpOutlinedIcon
            sx={{ fontSize: 16, color: tokens.brandPrimary }}
            aria-hidden="true"
          />
          <Typography sx={{ fontSize: '0.76rem', fontWeight: 700 }}>
            {approval.tier === 'T3' ? 'Tier T3 Refusal + Legal Alt' : 'Tier T2 Read-Back'}
          </Typography>
        </Box>
        <Typography
          variant="caption"
          className="mono-tabular"
          sx={{ color: tokens.textMuted, fontSize: '0.72rem' }}
        >
          nonce: {approval.approval_nonce}
        </Typography>
      </Box>

      <Typography
        sx={{
          fontSize: '0.82rem',
          fontWeight: 600,
          lineHeight: 1.35,
          color: isApproved ? tokens.legalPassText : tokens.textPrimary,
          mb: 1,
        }}
      >
        &ldquo;{approval.readback_text}&rdquo;
      </Typography>

      {/* Two Large Action Buttons side-by-side (Minimum 48x48px touch targets, §11.3 & §11.7) */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: '1.25fr 1fr',
          gap: 1,
        }}
      >
        <Button
          variant="contained"
          onClick={onApprove}
          aria-label="Approve plan and start outreach cascade"
          sx={{
            minHeight: 48,
            px: 1.5,
            fontSize: '0.84rem',
            fontWeight: 700,
            backgroundColor: tokens.brandPrimary,
            color: tokens.brandContrastText,
            '&:hover': {
              backgroundColor: tokens.brandPrimaryHover,
            },
          }}
        >
          <CheckIcon sx={{ mr: 0.5, fontSize: 18 }} aria-hidden="true" />
          {isApproved ? 'Approved (Running)' : 'Approve Plan (Yes)'}
        </Button>

        <Button
          variant="outlined"
          onClick={onRejectOrEdit}
          aria-label="Reject plan or edit constraints"
          sx={{
            minHeight: 48,
            px: 1.25,
            fontSize: '0.82rem',
            fontWeight: 600,
          }}
        >
          <EditNoteOutlinedIcon sx={{ mr: 0.5, fontSize: 18 }} aria-hidden="true" />
          {isRejected ? 'Re-solved' : 'No / Edit'}
        </Button>
      </Box>
    </Paper>
  );
};
