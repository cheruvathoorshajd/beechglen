import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { readKey, writeKey } from "../auth/session";
import { useFocusTrap } from "../hooks/useFocusTrap";
import { TOURS, type TourId } from "./tours";
import "./tour.css";

export const TOUR_KEY = "nexus911:tour";
const OPEN_EVENT = "nexus911:tour-open";

export function tourSeenKey(id: TourId) {
  return `${TOUR_KEY}:${id}`;
}

export function isTourSeen(id: TourId) {
  return readKey("local", tourSeenKey(id)) === "1";
}

function markTourSeen(id: TourId) {
  writeKey("local", tourSeenKey(id), "1");
}

/** Opens a page's tour, optionally at the step pointing at `target`. */
export function openTour(id: TourId, target?: string) {
  window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { id, target } }));
}

type Box = { top: number; left: number; width: number; height: number };

const PAD = 6;
const CARD_W = 340;
const GAP = 12;

function findTarget(target: string): HTMLElement | null {
  const nodes = Array.from(document.querySelectorAll<HTMLElement>(`[data-tour="${target}"]`));
  // In jsdom every rect is zero, so fall back to the first match.
  return nodes.find((node) => node.getClientRects().length > 0) ?? nodes[0] ?? null;
}

function measure(node: HTMLElement | null): Box | null {
  if (!node) return null;
  const rect = node.getBoundingClientRect();
  if (!rect.width && !rect.height) return null;
  return { top: rect.top - PAD, left: rect.left - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2 };
}

/** Card position: below the target, else above, else beside it; clamped to the viewport. */
function place(box: Box | null, cardHeight: number) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const width = Math.min(CARD_W, vw - 24);
  if (!box) return { top: Math.max(12, (vh - cardHeight) / 2), left: (vw - width) / 2, width };
  let top = box.top + box.height + GAP;
  if (top + cardHeight > vh - 12) top = box.top - cardHeight - GAP;
  let left = box.left;
  if (top < 12) {
    // No room above or below: put it beside the target.
    top = Math.min(Math.max(12, box.top), vh - cardHeight - 12);
    left = box.left + box.width + GAP + width <= vw - 12 ? box.left + box.width + GAP : box.left - width - GAP;
  }
  left = Math.min(Math.max(12, left), vw - width - 12);
  return { top: Math.max(12, top), left, width };
}

/**
 * A skippable coach-mark tour for one console page. Opens on the first visit,
 * and again from the "Guide" button or any "?" hint. Next / Back / Skip;
 * Escape skips; ←/→ move between steps.
 */
export function FeatureTour({ id, auto = import.meta.env.MODE !== "test" }: { id: TourId; auto?: boolean }) {
  const tour = TOURS[id];
  const [step, setStep] = useState<number | null>(null);
  const [box, setBox] = useState<Box | null>(null);
  const [cardHeight, setCardHeight] = useState(220);
  const card = useRef<HTMLDivElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const open = step !== null;
  const current = open ? tour.steps[step] : null;

  const start = useCallback(
    (target?: string) => {
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      const index = target ? tour.steps.findIndex((s) => s.target === target) : 0;
      setStep(Math.max(0, index));
    },
    [tour],
  );

  const close = useCallback(() => {
    markTourSeen(id);
    setStep(null);
    setBox(null);
    const back = opener.current;
    opener.current = null;
    if (back && document.contains(back)) back.focus({ preventScroll: true });
  }, [id]);

  // First visit: open once the page has painted.
  useEffect(() => {
    if (!auto || isTourSeen(id)) return;
    const timer = setTimeout(() => start(), 600);
    return () => clearTimeout(timer);
  }, [auto, id, start]);

  useEffect(() => {
    const onOpen = (event: Event) => {
      const detail = (event as CustomEvent<{ id: TourId; target?: string }>).detail;
      if (detail?.id === id) start(detail.target);
    };
    window.addEventListener(OPEN_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_EVENT, onOpen);
  }, [id, start]);

  // Point at the step's element and follow it on scroll and resize.
  useLayoutEffect(() => {
    if (!current) return;
    const node = findTarget(current.target);
    node?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setBox(measure(findTarget(current.target))));
    };
    setBox(measure(node));
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [current]);

  useLayoutEffect(() => {
    if (!open) return;
    title.current?.focus({ preventScroll: true });
    if (card.current) setCardHeight(card.current.offsetHeight || 220);
  }, [open, step]);

  useFocusTrap(card, open ? close : undefined);

  if (!open || !current) return <GuideButton id={id} onClick={() => start()} />;

  const last = step === tour.steps.length - 1;
  const present = box !== null;
  const position = place(box, cardHeight);
  const go = (next: number) => setStep(Math.min(Math.max(0, next), tour.steps.length - 1));

  return (
    <>
      <GuideButton id={id} onClick={() => start()} />
      <div className="tour-layer" aria-hidden="true" onClick={close}>
        {present ? (
          <div className="tour-spot" style={{ top: box.top, left: box.left, width: box.width, height: box.height }} />
        ) : (
          <div className="tour-veil" />
        )}
      </div>
      <div
        ref={card}
        className="tour-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        aria-describedby="tour-body"
        style={{ top: position.top, left: position.left, width: position.width }}
        onKeyDown={(event) => {
          const target = event.target as HTMLElement;
          if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;
          if (event.key === "ArrowRight" && !last) {
            event.preventDefault();
            go(step + 1);
          } else if (event.key === "ArrowLeft" && step > 0) {
            event.preventDefault();
            go(step - 1);
          }
        }}
      >
        <p className="tour-spec">
          {tour.title} · <span className="num">{String(step + 1).padStart(2, "0")}</span> / <span className="num">{String(tour.steps.length).padStart(2, "0")}</span>
        </p>
        <h2 id="tour-title" ref={title} tabIndex={-1}>
          {current.title}
        </h2>
        <p id="tour-body">{current.body}</p>
        {!present && current.missing && <p className="tour-missing">{current.missing}</p>}
        <div className="tour-dots" aria-hidden="true">
          {tour.steps.map((s, index) => (
            <i key={s.target} className={index === step ? "on" : index < step ? "done" : ""} />
          ))}
        </div>
        <div className="tour-actions">
          <button type="button" className="btn quiet sm" onClick={close}>
            Skip tour
          </button>
          <span className="flex-1" />
          {step > 0 && (
            <button type="button" className="btn ghost sm" onClick={() => go(step - 1)}>
              Back
            </button>
          )}
          <button type="button" className="btn primary sm" onClick={() => (last ? close() : go(step + 1))}>
            {last ? "Done" : "Next"}
          </button>
        </div>
      </div>
    </>
  );
}

function GuideButton({ id, onClick }: { id: TourId; onClick: () => void }) {
  return (
    <button type="button" className="tour-guide btn ghost sm" onClick={onClick} aria-label={`Open the ${TOURS[id].title} guide`}>
      <span aria-hidden="true" className="tour-q">
        ?
      </span>
      Guide
    </button>
  );
}

/** Small "?" next to a feature: opens the page tour at that feature's step. */
export function TourHint({ tour, target, label }: { tour: TourId; target: string; label: string }) {
  return (
    <button type="button" className="tour-hint" onClick={() => openTour(tour, target)} aria-label={`About ${label}`} title={`About ${label}`}>
      ?
    </button>
  );
}
