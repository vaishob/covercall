import React from 'react';
import { Box, Button, Paper, Typography, useTheme } from '@mui/material';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { SCENARIO_DESCRIPTORS, ScenarioKey } from '../mocks/state';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';

interface ScenarioLauncherProps {
  activeScenario: ScenarioKey;
  onSelectScenario: (key: ScenarioKey) => void;
}

export const ScenarioLauncher: React.FC<ScenarioLauncherProps> = ({
  activeScenario,
  onSelectScenario,
}) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;
  const isEmptyState = activeScenario === 'empty';
  const activeDesc = SCENARIO_DESCRIPTORS.find((d) => d.key === activeScenario);

  if (isEmptyState) {
    return (
      <Paper
        component="section"
        aria-label="Empty State Scenario Triggers"
        sx={{
          p: 2.5,
          backgroundColor: tokens.surface,
        }}
      >
        <Typography variant="h1" component="h1" sx={{ mb: 0.75 }}>
          No Active Shift Gap (Empty State)
        </Typography>
        <Typography variant="body2" sx={{ color: tokens.textSecondary, mb: 2 }}>
          Speak a sick call into Gemini Live (&ldquo;Ali can&apos;t make it, Bugis morning
          shift&rdquo;) or tap one of the three golden scenarios below to run CoverCall with no
          sign-in:
        </Typography>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
            gap: 1.5,
          }}
        >
          {SCENARIO_DESCRIPTORS.map((scen) => (
            <Button
              key={scen.key}
              variant="outlined"
              onClick={() => onSelectScenario(scen.key)}
              sx={{
                minHeight: 72,
                p: 1.5,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                textAlign: 'left',
                whiteSpace: 'normal',
                backgroundColor: tokens.surfaceSubtle,
                borderColor: tokens.borderStrong,
              }}
            >
              <Box
                sx={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 1,
                  mb: 0.5,
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                  <PlayCircleOutlineIcon sx={{ fontSize: 18, color: tokens.brandPrimary }} aria-hidden="true" />
                  <Typography component="span" sx={{ fontWeight: 700, fontSize: '0.95rem' }}>
                    {scen.buttonLabel}
                  </Typography>
                </Box>
                <Typography
                  component="span"
                  className="mono-tabular"
                  sx={{ fontSize: '0.72rem', fontWeight: 600, color: tokens.textMuted }}
                >
                  {scen.scenarioCode}
                </Typography>
              </Box>
              <Typography
                component="span"
                sx={{ fontSize: '0.82rem', color: tokens.textSecondary, lineHeight: 1.4 }}
              >
                {scen.oneLineSummary}
              </Typography>
            </Button>
          ))}
        </Box>
      </Paper>
    );
  }

  // Compact Scenario Bar when a scenario (like S-017) is active so Captions & Gap Card appear above the fold
  return (
    <Paper
      component="section"
      aria-label="Scenario Selector Bar"
      sx={{
        p: 1.25,
        backgroundColor: tokens.surface,
      }}
    >
      <Box
        role="group"
        aria-label="Scenario buttons"
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr 1fr', sm: 'repeat(4, auto)' },
          justifyContent: { sm: 'space-between' },
          gap: 0.75,
        }}
      >
        {SCENARIO_DESCRIPTORS.map((scen) => {
          const isSelected = activeScenario === scen.key;
          return (
            <Button
              key={scen.key}
              variant={isSelected ? 'contained' : 'outlined'}
              onClick={() => onSelectScenario(scen.key)}
              aria-pressed={isSelected}
              sx={{
                minHeight: 48,
                px: 1.25,
                py: 0.5,
                fontSize: '0.78rem',
                fontWeight: 700,
              }}
            >
              <PlayCircleOutlineIcon sx={{ fontSize: 15, mr: 0.5 }} aria-hidden="true" />
              {scen.buttonLabel}
            </Button>
          );
        })}

        <Button
          variant="outlined"
          onClick={() => onSelectScenario('empty')}
          aria-label="Switch to Empty State"
          sx={{
            minHeight: 48,
            px: 1.25,
            py: 0.5,
            fontSize: '0.76rem',
          }}
        >
          <RestartAltIcon sx={{ fontSize: 15, mr: 0.5 }} aria-hidden="true" />
          Empty State
        </Button>
      </Box>

      {activeDesc && (
        <Typography
          variant="caption"
          sx={{ display: 'block', color: tokens.textSecondary, mt: 0.75 }}
        >
          <strong className="mono-tabular">{activeDesc.scenarioCode}:</strong>{' '}
          {activeDesc.oneLineSummary}
        </Typography>
      )}
    </Paper>
  );
};
