import React, { useState } from 'react';
import {
  Box,
  Button,
  IconButton,
  TextField,
  Typography,
  useTheme,
} from '@mui/material';
import GraphicEqIcon from '@mui/icons-material/GraphicEq';
import PsychologyIcon from '@mui/icons-material/Psychology';
import RecordVoiceOverIcon from '@mui/icons-material/RecordVoiceOver';
import MicOffIcon from '@mui/icons-material/MicOff';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import MicIcon from '@mui/icons-material/Mic';
import TouchAppIcon from '@mui/icons-material/TouchApp';
import KeyboardIcon from '@mui/icons-material/Keyboard';
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined';
import LightModeOutlinedIcon from '@mui/icons-material/LightModeOutlined';
import SendIcon from '@mui/icons-material/Send';
import type { VoiceMode, VoiceState } from '../voice/types';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';

interface VoiceStateBarProps {
  voiceState: VoiceState;
  voiceMode: VoiceMode;
  voiceReason?: string;
  isReplay?: boolean;
  themeMode: 'light' | 'dark';
  onChangeVoiceState: (state: VoiceState) => void;
  onChangeVoiceMode: (mode: VoiceMode) => void;
  onToggleTheme: () => void;
  onSubmitUtterance: (text: string) => void;
}

const VOICE_STATES: VoiceState[] = ['Listening', 'Thinking', 'Speaking', 'Muted', 'Offline'];

export const VoiceStateBar: React.FC<VoiceStateBarProps> = ({
  voiceState,
  voiceMode,
  voiceReason,
  isReplay = false,
  themeMode,
  onChangeVoiceState,
  onChangeVoiceMode,
  onToggleTheme,
  onSubmitUtterance,
}) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;
  const [textDraft, setTextDraft] = useState('');

  const getStateIconAndStyle = (state: VoiceState) => {
    switch (state) {
      case 'Listening':
        return {
          icon: <GraphicEqIcon sx={{ fontSize: 16 }} aria-hidden="true" />,
          bg: tokens.legalPassBg,
          color: tokens.legalPassText,
          border: tokens.legalPassBorder,
          sublabel: 'Gemini Live v1alpha',
        };
      case 'Thinking':
        return {
          icon: <PsychologyIcon sx={{ fontSize: 16 }} aria-hidden="true" />,
          bg: tokens.amberAlertBg,
          color: tokens.amberAlertText,
          border: tokens.amberAlertBorder,
          sublabel: 'Awaiting API',
        };
      case 'Speaking':
        return {
          icon: <RecordVoiceOverIcon sx={{ fontSize: 16 }} aria-hidden="true" />,
          bg: tokens.legalPassBg,
          color: tokens.legalPassText,
          border: tokens.legalPassBorder,
          sublabel: 'Reading back plan',
        };
      case 'Muted':
        return {
          icon: <MicOffIcon sx={{ fontSize: 16 }} aria-hidden="true" />,
          bg: tokens.surfaceSubtle,
          color: tokens.textSecondary,
          border: tokens.borderStrong,
          sublabel: 'Mic muted',
        };
      case 'Offline':
        return {
          icon: <CloudOffIcon sx={{ fontSize: 16 }} aria-hidden="true" />,
          bg: tokens.ruleWarnBg,
          color: tokens.ruleWarnText,
          border: tokens.ruleWarnBorder,
          sublabel: isReplay
            ? 'Voice unavailable in recorded replay — text fallback'
            : 'Offline — text fallback',
        };
    }
  };

  const currentMeta = getStateIconAndStyle(voiceState);

  const cycleVoiceState = () => {
    const idx = VOICE_STATES.indexOf(voiceState);
    const next = VOICE_STATES[(idx + 1) % VOICE_STATES.length];
    onChangeVoiceState(next);
  };

  const handleTextSend = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = textDraft.trim();
    if (!trimmed) return;
    onSubmitUtterance(trimmed);
    setTextDraft('');
  };

  return (
    <Box
      component="header"
      role="banner"
      aria-label="CoverCall Voice State and Mode Controls"
      sx={{
        position: 'sticky',
        top: 0,
        zIndex: 30,
        backgroundColor: tokens.surface,
        borderBottom: `1px solid ${tokens.borderSubtle}`,
        px: 1.5,
        py: 0.75,
      }}
    >
      <Box
        sx={{
          maxWidth: 1080,
          mx: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 0.75,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 0.75,
          }}
        >
          {/* Brand + Voice State Indicator */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 1,
              width: { xs: '100%', sm: 'auto' },
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography
                component="span"
                sx={{
                  fontWeight: 700,
                  fontSize: '1.05rem',
                  letterSpacing: '-0.02em',
                  color: tokens.textPrimary,
                  whiteSpace: 'nowrap',
                }}
              >
                CoverCall
              </Typography>

              <Button
                onClick={cycleVoiceState}
                aria-label={`Voice state: ${voiceState} (${
                  voiceReason || currentMeta.sublabel
                }). Activate to inspect voice state indicator.`}
                sx={{
                  minHeight: 48,
                  minWidth: 48,
                  px: 1.25,
                  py: 0.5,
                  backgroundColor: currentMeta.bg,
                  color: currentMeta.color,
                  border: `1.5px solid ${currentMeta.border}`,
                  borderRadius: 2,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 0.6,
                  fontWeight: 700,
                  fontSize: '0.78rem',
                  '&:hover': {
                    backgroundColor: currentMeta.bg,
                    borderColor: currentMeta.color,
                  },
                }}
              >
                {currentMeta.icon}
                <span>{voiceState}</span>
              </Button>

              <Typography
                component="span"
                data-testid="voice-fallback-reason"
                sx={{
                  fontSize: '0.74rem',
                  fontWeight: 600,
                  color: tokens.textSecondary,
                }}
              >
                {voiceReason || currentMeta.sublabel}
              </Typography>
            </Box>

            <IconButton
              onClick={onToggleTheme}
              aria-label={
                themeMode === 'light' ? 'Switch to dark theme' : 'Switch to light theme'
              }
              sx={{
                display: { xs: 'inline-flex', sm: 'none' },
                minWidth: 48,
                minHeight: 48,
                border: `1px solid ${tokens.borderSubtle}`,
                color: tokens.textPrimary,
                backgroundColor: tokens.surfaceSubtle,
              }}
            >
              {themeMode === 'light' ? (
                <DarkModeOutlinedIcon fontSize="small" />
              ) : (
                <LightModeOutlinedIcon fontSize="small" />
              )}
            </IconButton>
          </Box>

          {/* Mode Switcher (Hands-free, Push-to-talk, Text) + Desktop Theme Toggle */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.75,
              width: { xs: '100%', sm: 'auto' },
            }}
          >
            <Box
              role="group"
              aria-label="Voice input mode switch"
              sx={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                width: { xs: '100%', sm: 'auto' },
                backgroundColor: tokens.surfaceSubtle,
                p: 0.25,
                borderRadius: 2,
                border: `1px solid ${tokens.borderSubtle}`,
              }}
            >
              {(
                [
                  {
                    id: 'hands-free',
                    label: 'Hands-free',
                    icon: <MicIcon sx={{ fontSize: 15 }} aria-hidden="true" />,
                  },
                  {
                    id: 'push-to-talk',
                    label: 'Push-to-talk',
                    icon: <TouchAppIcon sx={{ fontSize: 15 }} aria-hidden="true" />,
                  },
                  {
                    id: 'text',
                    label: 'Text',
                    icon: <KeyboardIcon sx={{ fontSize: 15 }} aria-hidden="true" />,
                  },
                ] as const
              ).map((item) => {
                const active = voiceMode === item.id;
                return (
                  <Button
                    key={item.id}
                    onClick={() => onChangeVoiceMode(item.id)}
                    aria-label={item.label}
                    aria-pressed={active}
                    sx={{
                      minHeight: 48,
                      minWidth: 48,
                      px: { xs: 1, sm: 1.5 },
                      py: 0.25,
                      borderRadius: 1.5,
                      fontSize: '0.76rem',
                      fontWeight: active ? 700 : 600,
                      backgroundColor: active ? tokens.brandPrimary : 'transparent',
                      color: active ? tokens.brandContrastText : tokens.textPrimary,
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 0.5,
                      '&:hover': {
                        backgroundColor: active ? tokens.brandPrimaryHover : tokens.surface,
                      },
                    }}
                  >
                    {item.icon}
                    <span>{item.label}</span>
                  </Button>
                );
              })}
            </Box>

            <IconButton
              onClick={onToggleTheme}
              aria-label={
                themeMode === 'light' ? 'Switch to dark theme' : 'Switch to light theme'
              }
              sx={{
                display: { xs: 'none', sm: 'inline-flex' },
                minWidth: 48,
                minHeight: 48,
                border: `1px solid ${tokens.borderSubtle}`,
                color: tokens.textPrimary,
                backgroundColor: tokens.surfaceSubtle,
              }}
            >
              {themeMode === 'light' ? (
                <DarkModeOutlinedIcon fontSize="small" />
              ) : (
                <LightModeOutlinedIcon fontSize="small" />
              )}
            </IconButton>
          </Box>
        </Box>

        {voiceMode === 'text' && (
          <Box
            component="form"
            onSubmit={handleTextSend}
            sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
          >
            <TextField
              size="small"
              fullWidth
              value={textDraft}
              onChange={(e) => setTextDraft(e.target.value)}
              placeholder="Type command (e.g., 'Ali can't make it, Bugis morning' or 'Yes, approve')"
              inputProps={{
                'aria-label': 'Lead text command input',
                style: { minHeight: '32px' },
              }}
            />
            <Button
              type="submit"
              variant="contained"
              aria-label="Send text command"
              sx={{ minHeight: 48, minWidth: 80, fontWeight: 700 }}
            >
              <SendIcon sx={{ fontSize: 15, mr: 0.5 }} aria-hidden="true" />
              Send
            </Button>
          </Box>
        )}
      </Box>
    </Box>
  );
};
