// Design primitives (.kiro/steering/style-guide.md → Components). Styles live in ui.css.
import {
  forwardRef,
  useId,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Link } from "react-router-dom";
import { Icon, type IconName } from "./Icon";

export { Icon } from "./Icon";
export type { IconName } from "./Icon";

const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(" ");

/* Wordmark ------------------------------------------------------------------ */

export function Wordmark({ to, className }: { to?: string; className?: string }) {
  const inner = (
    <>
      Nexus<b>911</b>
    </>
  );
  if (to) {
    return (
      <Link to={to} className={cx("wordmark", className)} aria-label="Nexus911 home">
        {inner}
      </Link>
    );
  }
  return (
    <span className={cx("wordmark", className)} aria-label="Nexus911">
      {inner}
    </span>
  );
}

/* Button -------------------------------------------------------------------- */

export type ButtonVariant = "primary" | "ghost" | "quiet";

export function buttonClass(variant: ButtonVariant = "ghost", size: "md" | "sm" = "md", block = false, extra?: string) {
  return cx("btn", variant, size === "sm" && "sm", block && "block", extra);
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "md" | "sm";
  block?: boolean;
  icon?: IconName;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "ghost", size = "md", block = false, icon, className, children, type = "button", ...rest },
  ref,
) {
  return (
    <button ref={ref} type={type} className={buttonClass(variant, size, block, className)} {...rest}>
      {children}
      {icon && <Icon name={icon} />}
    </button>
  );
});

/* Badge, Tag, SpecLabel ----------------------------------------------------- */

export type BadgeTone = "neutral" | "critical" | "highlight" | "warn" | "ok";

export function Badge({ tone = "neutral", children, className }: { tone?: BadgeTone; children: ReactNode; className?: string }) {
  return <span className={cx("badge", tone !== "neutral" && tone, className)}>{children}</span>;
}

export function Tag({ children }: { children: ReactNode }) {
  return <span className="tag">{children}</span>;
}

export function SpecLabel({ k, rest = [], as: As = "p", id }: { k: string; rest?: string[]; as?: "p" | "h2" | "div"; id?: string }) {
  return (
    <As className="spec" id={id}>
      <span className="k">{k}</span>
      {rest.map((part) => (
        <span key={part}>{part}</span>
      ))}
    </As>
  );
}

/* ConfidenceBar ------------------------------------------------------------- */

export function formatShare(share: number) {
  return `${Math.round(share * 100)}%`;
}

export function ConfidenceBar({
  value,
  tone = "ok",
  sources,
  firstHand,
  label,
}: {
  value: number;
  tone?: "ok" | "warn" | "soft";
  sources?: number;
  firstHand?: number;
  label?: string;
}) {
  const pct = Math.max(0, Math.min(1, value));
  const parts = [formatShare(pct)];
  if (sources !== undefined) parts.push(`${sources} ${sources === 1 ? "source" : "sources"}`);
  if (firstHand !== undefined) parts.push(`${firstHand} first-hand`);
  return (
    <div className="conf">
      {label !== undefined && <span className="text-[13.5px] text-ink">{label}</span>}
      <span className="conf-val">{parts.join(" · ")}</span>
      <div
        className="conf-track"
        style={{ gridColumn: "1 / -1" }}
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct * 100)}
        aria-label={label ? `${label} share` : "Share"}
      >
        <i className={cx("conf-fill", tone)} style={{ width: `${pct * 100}%` }} />
      </div>
    </div>
  );
}

/* Field --------------------------------------------------------------------- */

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
  help?: string;
};

export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { label, error, help, id, className, ...input },
  ref,
) {
  const auto = useId();
  const inputId = id ?? `f-${auto}`;
  const errId = `${inputId}-err`;
  const helpId = `${inputId}-help`;
  const describedBy = [error ? errId : null, help ? helpId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cx("field", className)}>
      <label htmlFor={inputId}>{label}</label>
      <input
        ref={ref}
        id={inputId}
        className={cx("inp", error && "bad")}
        aria-invalid={error ? true : false}
        aria-describedby={describedBy}
        {...input}
      />
      {error && (
        <p className="ferr" id={errId}>
          {error}
        </p>
      )}
      {help && (
        <p className="cap mt-3 border-l-2 border-rule pl-3" id={helpId}>
          {help}
        </p>
      )}
    </div>
  );
});

/* Roving radiogroup keys ---------------------------------------------------- */

export function nextIndex(key: string, index: number, count: number) {
  if (key === "ArrowRight" || key === "ArrowDown") return (index + 1) % count;
  if (key === "ArrowLeft" || key === "ArrowUp") return (index - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}

/* Segmented ----------------------------------------------------------------- */

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  disabled = false,
}: {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  disabled?: boolean;
}) {
  const current = Math.max(0, options.findIndex((o) => o.value === value));
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const next = nextIndex(event.key, current, options.length);
    if (next === null) return;
    event.preventDefault();
    event.stopPropagation();
    onChange(options[next].value);
    const buttons = event.currentTarget.querySelectorAll<HTMLButtonElement>("button");
    buttons[next]?.focus();
  };
  return (
    <div className="seg" role="radiogroup" aria-label={label} onKeyDown={onKeyDown}>
      {options.map((option, index) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          tabIndex={index === current ? 0 : -1}
          disabled={disabled}
          onClick={(event) => {
            event.stopPropagation();
            onChange(option.value);
          }}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/* ChoiceCard ---------------------------------------------------------------- */

export function ChoiceCard({
  title,
  body,
  tag,
  icon,
  go,
  selected = false,
  radio = false,
  disabled = false,
  tabIndex,
  onSelect,
  children,
  className,
}: {
  title: string;
  body: string;
  tag?: string;
  icon?: IconName;
  go?: string;
  selected?: boolean;
  radio?: boolean;
  disabled?: boolean;
  tabIndex?: number;
  onSelect?: () => void;
  children?: ReactNode;
  className?: string;
}) {
  const content = (
    <>
      {tag && <Tag>{tag}</Tag>}
      {icon && (
        <span className="icon-tile mb-2">
          <Icon name={icon} />
        </span>
      )}
      <span className="choice-t">{title}</span>
      <span className="choice-b">{body}</span>
      {children}
      {go && <span className="choice-go">{go}</span>}
      {radio && (
        <span className="choice-tick" aria-hidden="true">
          <Icon name="tick" />
        </span>
      )}
    </>
  );
  if (radio) {
    return (
      <div
        role="radio"
        aria-checked={selected}
        aria-disabled={disabled || undefined}
        tabIndex={tabIndex ?? (selected ? 0 : -1)}
        className={cx("choice radio", className)}
        onClick={() => !disabled && onSelect?.()}
        onKeyDown={(event) => {
          if ((event.key === " " || event.key === "Enter") && !disabled) {
            event.preventDefault();
            onSelect?.();
          }
        }}
      >
        {content}
      </div>
    );
  }
  return (
    <button type="button" className={cx("choice", selected && "selected", className)} disabled={disabled} onClick={onSelect}>
      {content}
    </button>
  );
}

/* Motifs -------------------------------------------------------------------- */

export function Disc({ className }: { className?: string }) {
  return <div className={cx("disc", className)} aria-hidden="true" />;
}

export function Bloom({ className }: { className?: string }) {
  return <div className={cx("bloom", className)} aria-hidden="true" />;
}

export function LiveDot({ live = true, label }: { live?: boolean; label?: string }) {
  return (
    <span className={cx("live", !live && "off")}>
      <i aria-hidden="true" />
      {label ?? (live ? "Live" : "Offline")}
    </span>
  );
}

export function Contested({ reason }: { reason?: string }) {
  return (
    <span className="inline-flex items-baseline gap-2">
      <span className="contested">△ Contested</span>
      {reason && <span className="text-[13px] text-ink-soft">{reason}</span>}
    </span>
  );
}
