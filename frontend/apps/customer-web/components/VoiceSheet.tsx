"use client";

/**
 * Voice input for the Clarity chat.
 *
 * Speech becomes text through the browser's own speech recognition
 * (`SpeechRecognition`). In Chrome and Safari that service sends the audio to
 * the browser vendor (Google, Apple), not to Hutch. Tapping Speak is the
 * opt-in: the sheet starts listening at once, inside that tap's user
 * activation, and says where the audio goes for as long as it listens. Only
 * the resulting text reaches Clarity, as an ordinary question the customer can
 * check or edit first. The orb reads the microphone's loudness locally and
 * sends nothing.
 *
 * The transcript is a hint like any typed text (I2): it goes through the same
 * turn pipeline and decides nothing by itself.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { t, type Lang } from "@clarity/i18n";
import { VoicePoweredOrb } from "@/components/ui/voice-powered-orb";

/* The DOM lib in TypeScript 5.4 does not declare the Web Speech API. */
type SpeechAlternative = { transcript: string };
type SpeechResult = { isFinal: boolean; 0: SpeechAlternative; length: number };
type SpeechResultEvent = { resultIndex: number; results: { length: number; [i: number]: SpeechResult } };
type SpeechErrorEvent = { error: string };
interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: SpeechResultEvent) => void) | null;
  onerror: ((e: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** Whether this browser can turn speech into text. Checked after mount, so server and client render the same. */
export function useVoiceSupported(): boolean {
  const [ok, setOk] = useState(false);
  useEffect(() => setOk(recognitionCtor() !== null), []);
  return ok;
}

const SPEECH_LANG: Record<Lang, string> = { en: "en-US", si: "si-LK", ta: "ta-LK" };

type Phase = "idle" | "listening" | "heard" | "error";
type ErrorKey = "voice.error.denied" | "voice.error.nospeech" | "voice.error.unavailable";

export function VoiceSheet({
  lang,
  onClose,
  onAsk,
  onEdit,
}: {
  lang: Lang;
  onClose: () => void;
  onAsk: (text: string) => void;
  onEdit: (text: string) => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [text, setText] = useState("");
  const [error, setError] = useState<ErrorKey | null>(null);
  const [voice, setVoice] = useState(false);
  const recRef = useRef<Recognition | null>(null);
  const textRef = useRef("");
  const primaryRef = useRef<HTMLButtonElement>(null);

  const stopRecognition = useCallback(() => {
    recRef.current?.abort();
    recRef.current = null;
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      stopRecognition();
    };
  }, [onClose, stopRecognition]);

  const start = () => {
    const Ctor = recognitionCtor();
    if (!Ctor) {
      setError("voice.error.unavailable");
      setPhase("error");
      return;
    }
    stopRecognition();
    const rec = new Ctor();
    rec.lang = SPEECH_LANG[lang] ?? "en-US";
    rec.continuous = false;
    rec.interimResults = true;
    textRef.current = "";
    setText("");
    setError(null);
    rec.onresult = (e) => {
      let all = "";
      for (let i = 0; i < e.results.length; i++) all += e.results[i][0].transcript;
      textRef.current = all.trim();
      setText(textRef.current);
    };
    rec.onerror = (e) => {
      const key: ErrorKey =
        e.error === "not-allowed" || e.error === "service-not-allowed" ? "voice.error.denied"
        : e.error === "no-speech" ? "voice.error.nospeech"
        : "voice.error.unavailable";
      if (e.error === "aborted") return;
      setError(key);
      setPhase("error");
    };
    rec.onend = () => {
      recRef.current = null;
      setPhase((p) => (p !== "listening" ? p : textRef.current ? "heard" : "error"));
      setError((err) => err ?? (textRef.current ? null : "voice.error.nospeech"));
    };
    recRef.current = rec;
    setPhase("listening");
    try {
      rec.start();
    } catch {
      setError("voice.error.unavailable");
      setPhase("error");
    }
  };

  const stop = () => recRef.current?.stop();

  // Listen as soon as the sheet opens: the Speak tap that opened it is the
  // user activation `start()` needs. A browser that still refuses lands in
  // the error state, whose Try again button is a fresh gesture.
  const startRef = useRef(start);
  startRef.current = start;
  useEffect(() => {
    startRef.current();
  }, []);

  // Keyboard focus follows the one action that matters in each phase.
  useEffect(() => {
    primaryRef.current?.focus();
  }, [phase]);

  const status =
    phase === "listening" ? (voice ? t(lang, "voice.hearing") : t(lang, "voice.listening"))
    : phase === "heard" ? t(lang, "voice.heard")
    : phase === "error" && error ? t(lang, error)
    : t(lang, "voice.hint");

  return (
    <div className="vo-backdrop" onClick={onClose}>
      <div
        className="vo-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="vo-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="vo-head">
          <h2 id="vo-title" className="vo-title">{t(lang, "voice.title")}</h2>
          <button type="button" className="vo-close" onClick={onClose} aria-label={t(lang, "voice.close")}>×</button>
        </div>

        <div className="vo-stage" data-phase={phase}>
          <VoicePoweredOrb enableVoiceControl={phase === "listening"} onVoiceDetected={setVoice} className="vo-stage-orb" />
        </div>

        <p className="vo-status" role="status" aria-live="polite" data-error={phase === "error" ? "" : undefined}>{status}</p>
        {text ? <p className="vo-transcript" data-testid="voice-transcript">{text}</p> : null}

        <p className="vo-notice">{t(lang, "voice.notice")}</p>

        <div className="vo-actions">
          {phase === "idle" || phase === "error" ? (
            <button ref={primaryRef} type="button" className="vo-btn vo-btn-primary" onClick={start}>
              {t(lang, phase === "idle" ? "voice.start" : "voice.retry")}
            </button>
          ) : null}
          {phase === "listening" ? (
            <button ref={primaryRef} type="button" className="vo-btn vo-btn-primary" onClick={stop}>{t(lang, "voice.stop")}</button>
          ) : null}
          {phase === "heard" ? (
            <>
              <button ref={primaryRef} type="button" className="vo-btn vo-btn-primary" onClick={() => onAsk(text)}>{t(lang, "voice.ask")}</button>
              <button type="button" className="vo-btn" onClick={() => onEdit(text)}>{t(lang, "voice.edit")}</button>
              <button type="button" className="vo-btn vo-btn-ghost" onClick={start}>{t(lang, "voice.retry")}</button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
