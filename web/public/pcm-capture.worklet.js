// AudioWorklet: capture mono mic frames and post them to the main thread, where src/voice/pcm.ts
// resamples them to 16 kHz PCM16 in 40 ms chunks. No audio is stored.
class PcmCapture extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch && ch.length) this.port.postMessage(ch.slice(0));
    return true;
  }
}
registerProcessor('pcm-capture', PcmCapture);
