import React from 'react';
import { Box, Button, Paper, Typography, useTheme } from '@mui/material';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import KeyOutlinedIcon from '@mui/icons-material/KeyOutlined';
import { RosterOutletRow } from '../mocks/state';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { MockDataBadge } from './MockDataBadge';

interface RosterMiniGridProps {
  rows: RosterOutletRow[];
  selectedAssigneeName: string;
  isReSolving: boolean;
  isMockMode?: boolean;
  onTriggerReSolve: () => void;
}

export const RosterMiniGrid: React.FC<RosterMiniGridProps> = ({
  rows,
  selectedAssigneeName,
  isReSolving,
  isMockMode = true,
  onTriggerReSolve,
}) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  const hours = rows[0]?.cells.map((c) => c.hourLabel) ?? [
    '7am',
    '8am',
    '9am',
    '10am',
    '11am',
    '12pm',
    '1pm',
    '2pm',
  ];

  return (
    <Paper
      component="section"
      aria-label="Multi-Outlet Live Roster Mini-Grid"
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
              Roster Mini-Grid (Outlets × Hour)
            </Typography>
            <MockDataBadge isMockMode={isMockMode} />
          </Box>
          <Typography variant="body2" sx={{ color: tokens.textSecondary }}>
            Bugis, Tampines, and Jurong East morning window
          </Typography>
        </Box>

        <Button
          variant="outlined"
          size="small"
          onClick={onTriggerReSolve}
          aria-label="Preview roster grid update"
          sx={{ minHeight: 48, fontSize: '0.8rem' }}
        >
          <AutorenewIcon sx={{ fontSize: 18, mr: 0.75 }} aria-hidden="true" />
          Preview Grid Update
        </Button>
      </Box>

      {/* Responsive Grid Table */}
      <Box
        sx={{
          overflowX: 'auto',
          opacity: isReSolving ? 0.65 : 1,
          transform: isReSolving ? 'scale(0.992)' : 'scale(1)',
          transition:
            'opacity 180ms cubic-bezier(0.16, 1, 0.3, 1), transform 180ms cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        <Box
          component="table"
          aria-label="Outlets hourly coverage schedule"
          sx={{
            width: '100%',
            borderCollapse: 'separate',
            borderSpacing: '4px',
            minWidth: 320,
          }}
        >
          <thead>
            <tr>
              <Box
                component="th"
                scope="col"
                sx={{
                  textAlign: 'left',
                  p: 0.75,
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  color: tokens.textSecondary,
                }}
              >
                Outlet
              </Box>
              {hours.map((hr) => (
                <Box
                  component="th"
                  scope="col"
                  key={hr}
                  className="mono-tabular"
                  sx={{
                    textAlign: 'center',
                    p: 0.5,
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    color: tokens.textMuted,
                  }}
                >
                  {hr}
                </Box>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.outletId}>
                <Box
                  component="th"
                  scope="row"
                  sx={{
                    textAlign: 'left',
                    p: 0.75,
                    whiteSpace: 'nowrap',
                    verticalAlign: 'middle',
                  }}
                >
                  <Typography sx={{ fontSize: '0.84rem', fontWeight: 700 }}>
                    {row.outletName}
                  </Typography>
                  <Box
                    sx={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 0.4,
                      color: tokens.textMuted,
                      fontSize: '0.7rem',
                    }}
                  >
                    <KeyOutlinedIcon sx={{ fontSize: 12 }} aria-hidden="true" />
                    <span>{row.station}</span>
                  </Box>
                </Box>

                {row.cells.map((cell) => {
                  const isBugisTarget = row.outletId === 'bugis';
                  const displayStaff = isBugisTarget
                    ? cell.hourLabel === '12pm'
                      ? '45m Break'
                      : selectedAssigneeName.split(' ')[0]
                    : cell.staffName;

                  return (
                    <Box
                      component="td"
                      key={cell.hourLabel}
                      sx={{
                        p: 0.6,
                        textAlign: 'center',
                        borderRadius: 1.5,
                        backgroundColor: isBugisTarget
                          ? tokens.legalPassBg
                          : tokens.surfaceSubtle,
                        color: isBugisTarget ? tokens.legalPassText : tokens.textSecondary,
                        border: `1px solid ${
                          isBugisTarget ? tokens.legalPassBorder : tokens.borderSubtle
                        }`,
                        fontSize: '0.72rem',
                        fontWeight: isBugisTarget ? 700 : 500,
                      }}
                    >
                      {displayStaff}
                    </Box>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </Box>
      </Box>
    </Paper>
  );
};
