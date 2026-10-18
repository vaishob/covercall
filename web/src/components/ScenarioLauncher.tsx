import React from 'react';
import { Box, Button, Paper, Typography, useTheme } from '@mui/material';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import type { ScenarioDto } from '../data/backendTypes';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';

interface ScenarioLauncherProps {
  scenarios: ScenarioDto[];
  activeScenarioId: string | null;
  busy: boolean;
  onStart: (scenarioId: string) => void;
}

/** One-tap Scenario buttons (§11.3 empty state). The list comes from GET /scenarios. */
export const ScenarioLauncher: React.FC<ScenarioLauncherProps> = ({ scenarios, activeScenarioId, busy, onStart }) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;
  const compact = activeScenarioId !== null;

  return (
    <Paper component="section" aria-labelledby="scenario-heading" sx={{ p: compact ? 1.25 : 2.5, backgroundColor: tokens.surface }}>
      <Typography id="scenario-heading" variant={compact ? 'h2' : 'h1'} component="h1" sx={{ mb: compact ? 0.75 : 1 }}>
        {compact ? 'Scenarios' : 'No active shift gap'}
      </Typography>
      {!compact && (
        <Typography variant="body2" sx={{ color: tokens.textSecondary, mb: 2 }}>
          Tap a scenario to run CoverCall end to end. No sign-in.
        </Typography>
      )}
      <Box
        role="group"
        aria-label="Scenario buttons"
        sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: `repeat(${Math.max(1, scenarios.length)}, 1fr)` }, gap: 1.25 }}
      >
        {scenarios.map((s) => {
          const selected = s.scenario_id === activeScenarioId;
          return (
            <Button
              key={s.scenario_id}
              variant={selected ? 'contained' : 'outlined'}
              aria-pressed={selected}
              disabled={busy}
              onClick={() => onStart(s.scenario_id)}
              sx={{
                minHeight: compact ? 48 : 72,
                p: 1.25,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                textAlign: 'left',
                whiteSpace: 'normal',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, width: '100%', justifyContent: 'space-between' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                  <PlayCircleOutlineIcon sx={{ fontSize: 18 }} aria-hidden="true" />
                  <span style={{ fontWeight: 700 }}>{s.label}</span>
                </Box>
                <span className="mono-tabular" style={{ fontSize: '0.72rem' }}>
                  {s.scenario_id} · {s.journey}
                </span>
              </Box>
              {!compact && (
                <Typography component="span" sx={{ fontSize: '0.82rem', mt: 0.5 }}>
                  {s.description}
                </Typography>
              )}
            </Button>
          );
        })}
      </Box>
    </Paper>
  );
};
