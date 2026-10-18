export type VoiceState = 'Listening' | 'Thinking' | 'Speaking' | 'Muted' | 'Offline';
export type VoiceMode = 'hands-free' | 'push-to-talk' | 'text';

export interface CaptionExchange {
  id: string;
  speaker: 'Lead' | 'CoverCall';
  timestampIso: string;
  text: string;
  highlight?: boolean;
}
