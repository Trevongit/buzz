const DEFAULT_OUTPUT_SAMPLE_RATE = 24_000;

function writeAscii(view: DataView, offset: number, value: string) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

export function encodeVoiceNoteWav(
  channels: readonly Float32Array[],
  inputSampleRate: number,
  outputSampleRate = DEFAULT_OUTPUT_SAMPLE_RATE,
): Uint8Array {
  const inputLength = channels[0]?.length ?? 0;
  if (
    channels.length === 0 ||
    inputLength === 0 ||
    !Number.isFinite(inputSampleRate) ||
    inputSampleRate <= 0 ||
    !Number.isFinite(outputSampleRate) ||
    outputSampleRate <= 0
  ) {
    throw new Error("Cannot encode an empty voice note");
  }

  const frameCount = Math.max(
    1,
    Math.floor((inputLength * outputSampleRate) / inputSampleRate),
  );
  const bytes = new Uint8Array(44 + frameCount * 2);
  const view = new DataView(bytes.buffer);
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, bytes.length - 8, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, outputSampleRate, true);
  view.setUint32(28, outputSampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, frameCount * 2, true);

  const ratio = inputSampleRate / outputSampleRate;
  for (let outputIndex = 0; outputIndex < frameCount; outputIndex += 1) {
    const sourcePosition = outputIndex * ratio;
    const leftIndex = Math.min(inputLength - 1, Math.floor(sourcePosition));
    const rightIndex = Math.min(inputLength - 1, leftIndex + 1);
    const mix = sourcePosition - leftIndex;
    let sample = 0;
    for (const channel of channels) {
      const left = channel[leftIndex] ?? 0;
      const right = channel[rightIndex] ?? left;
      sample += left + (right - left) * mix;
    }
    sample = Math.max(-1, Math.min(1, sample / channels.length));
    view.setInt16(
      44 + outputIndex * 2,
      sample < 0 ? sample * 0x8000 : sample * 0x7fff,
      true,
    );
  }

  return bytes;
}

/** Peak we aim for after auto-boost. Leaves a little headroom. */
export const VOICE_NOTE_TARGET_PEAK = 0.89;
/** Cap so a near-silent room is not slammed into hiss. About +21 dB. */
export const VOICE_NOTE_MAX_BOOST = 12;

export function peakOfPcm(pcm: Float32Array): number {
  let peak = 0;
  for (const sample of pcm) {
    const magnitude = Math.abs(sample);
    if (magnitude > peak) peak = magnitude;
  }
  return peak;
}

/**
 * Lift quiet speech toward a strong recording level without clipping.
 * Returns a new buffer. Silence stays silence.
 */
export function autoBoostPcm(
  pcm: Float32Array,
  targetPeak = VOICE_NOTE_TARGET_PEAK,
  maxGain = VOICE_NOTE_MAX_BOOST,
): { pcm: Float32Array; gain: number } {
  const peak = peakOfPcm(pcm);
  if (peak < 1e-4) {
    return { pcm, gain: 1 };
  }
  const gain = Math.min(maxGain, Math.max(1, targetPeak / peak));
  if (gain <= 1.01) {
    return { pcm, gain: 1 };
  }
  const boosted = new Float32Array(pcm.length);
  for (let index = 0; index < pcm.length; index += 1) {
    boosted[index] = Math.max(-1, Math.min(1, pcm[index] * gain));
  }
  return { pcm: boosted, gain };
}
