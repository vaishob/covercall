import test from 'node:test';
import assert from 'node:assert/strict';
import { fallbackModeFor, isSameModeActive, liveReadyState, talkState } from './voiceFlow.ts';

test('fallbackModeFor: 429 and mic denial skip push-to-talk; other failures follow the chain', () => {
  assert.equal(fallbackModeFor({ status: 429 }, 'push-to-talk'), 'text');
  assert.equal(fallbackModeFor({ micDenied: true }, 'push-to-talk'), 'text');
  assert.equal(fallbackModeFor({ status: 501 }, 'push-to-talk'), 'push-to-talk');
  assert.equal(fallbackModeFor({ status: 502 }, 'push-to-talk'), 'push-to-talk');
  assert.equal(fallbackModeFor({}, 'push-to-talk'), 'push-to-talk'); // socket error
  assert.equal(fallbackModeFor({}, 'text'), 'text');
});

test('liveReadyState: Listening only when audio runs; suspended audio asks for a tap', () => {
  assert.deepEqual(liveReadyState(false, true), { state: 'Listening', needsTap: false });
  assert.deepEqual(liveReadyState(true, true), { state: 'Muted', needsTap: false });
  assert.deepEqual(liveReadyState(false, false), { state: 'Muted', needsTap: true });
  assert.deepEqual(liveReadyState(true, false), { state: 'Muted', needsTap: true });
});

test('talkState: no live session never yields Listening', () => {
  assert.equal(talkState(true, false), null);
  assert.equal(talkState(false, false), null);
  assert.equal(talkState(true, true), 'Listening');
  assert.equal(talkState(false, true), 'Muted');
});

test('isSameModeActive: re-tapping a connected or connecting mode is a no-op; Offline reconnects', () => {
  assert.equal(isSameModeActive('hands-free', 'hands-free', 'Listening', true), true);
  assert.equal(isSameModeActive('hands-free', 'hands-free', 'Thinking', true), true); // mint in flight
  assert.equal(isSameModeActive('hands-free', 'hands-free', 'Offline', true), false);
  assert.equal(isSameModeActive('push-to-talk', 'hands-free', 'Listening', true), false);
  assert.equal(isSameModeActive('hands-free', 'hands-free', 'Muted', false), false);
});
