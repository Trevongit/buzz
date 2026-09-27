import * as React from "react";

import {
  autoBoostPcm,
  encodeVoiceNoteWav,
  VOICE_NOTE_MAX_BOOST,
  VOICE_NOTE_TARGET_PEAK,
} from "./voiceNoteWav";

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/ogg;codecs=opus",
  "audio/mp4",
  "audio/webm",
] as const;

function supportedMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type));
}

function concatPcm(chunks: readonly Float32Array[]): Float32Array {
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const out = new Float32Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}

function applyMicGain(
  pcm: Float32Array,
  autoBoost: boolean,
  manualGain: number,
): Float32Array {
  if (autoBoost) return autoBoostPcm(pcm).pcm;
  if (manualGain <= 1.01) return pcm;
  const scaled = new Float32Array(pcm.length);
  for (let index = 0; index < pcm.length; index += 1) {
    scaled[index] = Math.max(-1, Math.min(1, pcm[index] * manualGain));
  }
  return scaled;
}

function wavFromPcm(
  pcm: Float32Array,
  sampleRate: number,
  autoBoost: boolean,
  manualGain: number,
): VoiceNoteRecording | null {
  if (pcm.length === 0 || sampleRate <= 0) return null;
  const wav = encodeVoiceNoteWav(
    [applyMicGain(pcm, autoBoost, manualGain)],
    sampleRate,
  );
  const wavBuffer = new ArrayBuffer(wav.byteLength);
  new Uint8Array(wavBuffer).set(wav);
  return {
    duration: pcm.length / sampleRate,
    file: new File([wavBuffer], `voice-note-${Date.now()}.wav`, {
      type: "audio/wav",
    }),
  };
}

export type VoiceNoteRecording = {
  duration: number;
  file: File;
};

type RecordingSession = {
  cancelled: boolean;
  chunks: Blob[];
  context: AudioContext | null;
  mute: GainNode | null;
  pcm: Float32Array[];
  runningPeak: number;
  processor: ScriptProcessorNode | null;
  recorder: MediaRecorder | null;
  resolveStop: ((recording: VoiceNoteRecording | null) => void) | null;
  sampleRate: number;
  startedAt: number;
  stream: MediaStream | null;
};

function releaseSessionAudio(session: RecordingSession) {
  session.processor?.disconnect();
  session.processor = null;
  session.mute?.disconnect();
  session.mute = null;
  session.stream?.getTracks().forEach((track) => {
    track.stop();
  });
  session.stream = null;
  const context = session.context;
  session.context = null;
  if (context) void context.close().catch(() => undefined);
}

async function acquireMicrophone(): Promise<MediaStream> {
  const devices = navigator.mediaDevices;
  if (!devices?.getUserMedia) {
    throw new Error("getUserMedia missing");
  }
  try {
    return await devices.getUserMedia({
      audio: {
        autoGainControl: true,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
  } catch {
    return devices.getUserMedia({ audio: true });
  }
}

export function useVoiceNoteRecorder() {
  const mountedRef = React.useRef(true);
  const sessionRef = React.useRef<RecordingSession | null>(null);
  const [status, setStatus] = React.useState<
    "idle" | "requesting" | "recording" | "processing"
  >("idle");
  const [elapsedSeconds, setElapsedSeconds] = React.useState(0);
  const [levels, setLevels] = React.useState<number[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [autoBoost, setAutoBoost] = React.useState(true);
  const [manualGain, setManualGain] = React.useState(2);
  const [liveBoost, setLiveBoost] = React.useState(1);
  const autoBoostRef = React.useRef(autoBoost);
  const manualGainRef = React.useRef(manualGain);
  autoBoostRef.current = autoBoost;
  manualGainRef.current = manualGain;

  const cancel = React.useCallback(() => {
    const session = sessionRef.current;
    if (!session) return;
    session.cancelled = true;
    sessionRef.current = null;
    session.resolveStop?.(null);
    session.resolveStop = null;
    const recorder = session.recorder;
    if (recorder && recorder.state !== "inactive") {
      try {
        recorder.stop();
      } catch {
        // PCM capture still needs the stream released.
      }
    }
    releaseSessionAudio(session);
    if (mountedRef.current) {
      setStatus("idle");
      setElapsedSeconds(0);
    }
  }, []);

  const finishRecording = React.useCallback(
    async (
      session: RecordingSession,
      mimeType?: string,
    ): Promise<VoiceNoteRecording | null> => {
      let recording: VoiceNoteRecording | null = null;
      if (!session.cancelled) {
        recording = wavFromPcm(
          concatPcm(session.pcm),
          session.sampleRate,
          autoBoostRef.current,
          manualGainRef.current,
        );
        if (!recording && session.chunks.length > 0 && session.context) {
          try {
            const actualMime =
              session.recorder?.mimeType || mimeType || "audio/webm";
            const blob = new Blob(session.chunks, { type: actualMime });
            if (blob.size > 0) {
              const encoded = await blob.arrayBuffer();
              const decoded = await session.context.decodeAudioData(
                encoded.slice(0),
              );
              if (
                !session.cancelled &&
                mountedRef.current &&
                sessionRef.current === session
              ) {
                const frameCount = decoded.getChannelData(0).length;
                const mixed = new Float32Array(frameCount);
                const channelCount = Math.max(1, decoded.numberOfChannels);
                for (let index = 0; index < frameCount; index += 1) {
                  let sample = 0;
                  for (let channel = 0; channel < channelCount; channel += 1) {
                    sample += decoded.getChannelData(channel)[index] ?? 0;
                  }
                  mixed[index] = sample / channelCount;
                }
                const wav = encodeVoiceNoteWav(
                  [
                    applyMicGain(
                      mixed,
                      autoBoostRef.current,
                      manualGainRef.current,
                    ),
                  ],
                  decoded.sampleRate,
                );
                const wavBuffer = new ArrayBuffer(wav.byteLength);
                new Uint8Array(wavBuffer).set(wav);
                recording = {
                  duration: decoded.duration,
                  file: new File([wavBuffer], `voice-note-${Date.now()}.wav`, {
                    type: "audio/wav",
                  }),
                };
              }
            }
          } catch {
            if (
              !session.cancelled &&
              mountedRef.current &&
              sessionRef.current === session
            ) {
              setError("Buzz could not prepare this voice note for upload.");
            }
          }
        }
        if (
          !recording &&
          !session.cancelled &&
          mountedRef.current &&
          sessionRef.current === session
        ) {
          setError("Buzz could not prepare this voice note for upload.");
        }
      }
      releaseSessionAudio(session);
      if (sessionRef.current === session) {
        sessionRef.current = null;
        if (mountedRef.current) {
          setStatus("idle");
          setElapsedSeconds(0);
        }
      }
      session.resolveStop?.(recording);
      session.resolveStop = null;
      return recording;
    },
    [],
  );

  const start = React.useCallback(async () => {
    if (status !== "idle" || sessionRef.current) return;
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Voice recording is not available in this environment.");
      return;
    }

    const session: RecordingSession = {
      cancelled: false,
      chunks: [],
      context: null,
      mute: null,
      pcm: [],
      runningPeak: 1e-4,
      processor: null,
      recorder: null,
      resolveStop: null,
      sampleRate: 0,
      startedAt: 0,
      stream: null,
    };
    sessionRef.current = session;
    setStatus("requesting");

    try {
      const stream = await acquireMicrophone();
      session.stream = stream;
      if (
        session.cancelled ||
        !mountedRef.current ||
        sessionRef.current !== session
      ) {
        releaseSessionAudio(session);
        return;
      }

      const AudioCtx =
        window.AudioContext ||
        (window as typeof window & { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext;
      if (!AudioCtx) {
        throw new Error("AudioContext missing");
      }
      const context = new AudioCtx();
      session.context = context;
      session.sampleRate = context.sampleRate;
      if (context.state === "suspended") {
        await context.resume().catch(() => undefined);
      }
      const source = context.createMediaStreamSource(stream);
      const analyser = context.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.72;
      source.connect(analyser);

      const processorHost = context as AudioContext & {
        createScriptProcessor?: (
          bufferSize: number,
          inputChannels: number,
          outputChannels: number,
        ) => ScriptProcessorNode;
      };
      const processor =
        processorHost.createScriptProcessor?.(4096, 1, 1) ?? null;
      session.processor = processor;
      if (processor) {
        processor.onaudioprocess = (event) => {
          if (session.cancelled || sessionRef.current !== session) return;
          const input = event.inputBuffer.getChannelData(0);
          let blockPeak = 0;
          for (const sample of input) {
            const magnitude = Math.abs(sample);
            if (magnitude > blockPeak) blockPeak = magnitude;
          }
          session.runningPeak = Math.max(
            session.runningPeak * 0.997,
            blockPeak,
          );
          session.pcm.push(new Float32Array(input));
        };
        const mute = context.createGain();
        mute.gain.value = 0;
        session.mute = mute;
        source.connect(processor);
        processor.connect(mute);
        mute.connect(context.destination);
      }

      const mimeType = supportedMimeType();
      if (typeof MediaRecorder !== "undefined") {
        try {
          const recorder = mimeType
            ? new MediaRecorder(stream, { mimeType })
            : new MediaRecorder(stream);
          session.recorder = recorder;
          recorder.addEventListener("dataavailable", (event) => {
            if (event.data.size > 0) session.chunks.push(event.data);
          });
          recorder.addEventListener("stop", () => {
            void finishRecording(session, mimeType);
          });
          recorder.addEventListener("error", () => {
            if (mountedRef.current && sessionRef.current === session) {
              setError("The voice recording was interrupted.");
            }
          });
          recorder.start(250);
        } catch {
          session.recorder = null;
        }
      }

      session.startedAt = performance.now();
      setElapsedSeconds(0);
      setLevels([]);
      setLiveBoost(1);
      setStatus("recording");

      const samples = new Uint8Array(analyser.fftSize);
      const levelTimer = window.setInterval(() => {
        if (session.cancelled || sessionRef.current !== session) {
          window.clearInterval(levelTimer);
          return;
        }
        analyser.getByteTimeDomainData(samples);
        let sumSquares = 0;
        for (const sample of samples) {
          const centered = (sample - 128) / 128;
          sumSquares += centered * centered;
        }
        const rms = Math.sqrt(sumSquares / samples.length);
        const liveGain = autoBoostRef.current
          ? Math.min(
              VOICE_NOTE_MAX_BOOST,
              Math.max(1, VOICE_NOTE_TARGET_PEAK / session.runningPeak),
            )
          : manualGainRef.current;
        const level = Math.min(1, rms * 5.5 * Math.min(4, liveGain) * 0.45);
        if (!mountedRef.current) return;
        setLiveBoost(liveGain);
        setLevels((previous) => [...previous, level]);
        setElapsedSeconds((performance.now() - session.startedAt) / 1000);
      }, 90);
    } catch (cause) {
      releaseSessionAudio(session);
      if (
        session.cancelled ||
        !mountedRef.current ||
        sessionRef.current !== session
      ) {
        return;
      }
      sessionRef.current = null;
      setStatus("idle");
      const denied =
        cause instanceof DOMException &&
        (cause.name === "NotAllowedError" || cause.name === "SecurityError");
      setError(
        denied
          ? "Allow Buzz to access your microphone to record a voice note."
          : "Buzz could not start the voice recorder.",
      );
    }
  }, [finishRecording, status]);

  const stop = React.useCallback(
    (discard = false): Promise<VoiceNoteRecording | null> => {
      if (discard) {
        cancel();
        return Promise.resolve(null);
      }
      const session = sessionRef.current;
      if (!session) return Promise.resolve(null);
      setStatus("processing");
      const recorder = session.recorder;
      if (recorder && recorder.state !== "inactive") {
        return new Promise((resolve) => {
          session.resolveStop = resolve;
          try {
            recorder.stop();
          } catch {
            void finishRecording(session).then(resolve);
          }
        });
      }
      return finishRecording(session);
    },
    [cancel, finishRecording],
  );

  React.useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      cancel();
    };
  }, [cancel]);

  return {
    autoBoost,
    cancel,
    elapsedSeconds,
    error,
    levels,
    liveBoost,
    manualGain,
    setAutoBoost,
    setManualGain,
    start,
    status,
    stop,
  };
}
