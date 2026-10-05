"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useSidebarCollapse } from "./SidebarCollapseContext";
import { useStaffSession } from "./StaffSessionProvider";

const links: { href: string; label: string; anyOf: string[]; icon: ReactNode }[] = [
  { href: "/desk", label: "Cases", anyOf: ["desk:queue:read"], icon: <IconCases /> },
  { href: "/insights", label: "Insights", anyOf: ["desk:queue:read"], icon: <IconInsights /> },
  { href: "/autopsy", label: "Complaint Autopsy", anyOf: ["desk:queue:read"], icon: <IconAutopsy /> },
  // `foresight:read`, which the page itself requires (C4). Gating the link on
  // the desk's permission instead offered every agent and supervisor a link
  // that lands on "access denied": the nav must promise what the page keeps.
  { href: "/foresight", label: "Foresight", anyOf: ["foresight:read"], icon: <IconForesight /> },
  {
    // The same two the Policy Studio page and the governance routes check
    // (D3). `rule:publish` was in here and is held by compliance, who holds
    // neither config permission, so they were shown a link to a refusal.
    href: "/studio",
    label: "Studio",
    anyOf: ["config:draft", "config:approve"],
    icon: <IconStudio />,
  },
  { href: "/audit", label: "Audit", anyOf: ["audit:read"], icon: <IconAudit /> },
  { href: "/admin", label: "Admin", anyOf: ["admin:manage", "flags:kill_switch"], icon: <IconAdmin /> },
];

type Slider = { top: number; height: number; ready: boolean };

/**
 * The section navigation (E2).
 *
 * Orange rail, white idle labels, soft orange hover pill. A single sliding
 * tab (workspace `bg` colour) moves between sections so the change is smooth.
 * Only permitted sections appear; the shell mounts this after sign-in.
 */
export function ConsoleNav() {
  const pathname = usePathname();
  const { hasPermission } = useStaffSession();
  const { collapsed, toggle } = useSidebarCollapse();
  const visible = links.filter((link) => hasPermission(...link.anyOf));
  const trackRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Map<string, HTMLLIElement>>(new Map());
  const [slider, setSlider] = useState<Slider>({ top: 0, height: 0, ready: false });

  const activeHref =
    visible.find(
      (link) => pathname === link.href || pathname?.startsWith(`${link.href}/`),
    )?.href ?? null;

  useLayoutEffect(() => {
    const track = trackRef.current;
    if (!track || !activeHref) {
      setSlider((prev) => ({ ...prev, ready: false }));
      return;
    }

    function place() {
      const item = itemRefs.current.get(activeHref!);
      if (!track || !item) return;
      const trackBox = track.getBoundingClientRect();
      const itemBox = item.getBoundingClientRect();
      setSlider({
        top: itemBox.top - trackBox.top,
        height: itemBox.height,
        ready: true,
      });
    }

    // Wait one frame so width/padding from expand-collapse have applied.
    const frame = window.requestAnimationFrame(place);
    window.addEventListener("resize", place);
    const ro =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(place);
    ro?.observe(track);
    return () => {
      window.cancelAnimationFrame(frame);
      ro?.disconnect();
      window.removeEventListener("resize", place);
    };
  }, [activeHref, visible.length, collapsed]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        className={
          collapsed
            ? "flex flex-col gap-3 pb-2 pt-5 pl-2 pr-0"
            : "flex items-center gap-2 px-3 pb-2 pt-5"
        }
      >
        <Link
          href="/"
          className={
            collapsed
              ? "flex items-center justify-center py-3 pl-3 pr-2"
              : "flex min-w-0 flex-1 items-center justify-center"
          }
          title="Hutch Clarity Desk"
        >
          {/* Expanded: full wordmark. Collapsed: mark-only logo. */}
          <img
            src={collapsed ? "/hutch-clarity-mark.png" : "/hutch-clarity-logo.png"}
            alt="Hutch Clarity"
            className={
              collapsed
                ? "h-8 w-8 object-contain"
                : "mx-auto h-12 w-auto max-w-[196px] object-contain object-center"
            }
          />
        </Link>
        <button
          type="button"
          onClick={toggle}
          aria-expanded={!collapsed}
          aria-controls="console-main"
          className={
            collapsed
              ? "flex w-full items-center justify-center py-3 pl-3 pr-2 text-white/85 transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
              : "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-white/85 transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
          }
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <span className="sr-only">
            {collapsed ? "Expand sidebar" : "Collapse sidebar"}
          </span>
          <PanelToggleIcon collapsed={collapsed} />
        </button>
      </div>
      <nav
        aria-label="Console sections"
        className={`pb-4 pt-5 pr-0 ${collapsed ? "pl-2" : "pl-3"}`}
      >
        <div ref={trackRef} className="relative">
          <div
            aria-hidden="true"
            className="console-nav-slider"
            style={{
              top: slider.top,
              height: slider.height,
              opacity: slider.ready ? 1 : 0,
            }}
          />
          <ul className="relative z-10 flex flex-col gap-3">
            {visible.map((link) => {
              const active = link.href === activeHref;
              return (
                <li
                  key={link.href}
                  ref={(node) => {
                    if (node) itemRefs.current.set(link.href, node);
                    else itemRefs.current.delete(link.href);
                  }}
                  className={active || collapsed ? undefined : "pr-4"}
                >
                  <Link
                    href={link.href}
                    aria-current={active ? "page" : undefined}
                    title={collapsed ? link.label : undefined}
                    className={
                      collapsed
                        ? `flex items-center justify-center py-3 pl-3 pr-2 transition-colors duration-300 ${
                            active ? "font-semibold" : "font-medium text-white"
                          }`
                        : active
                          ? "flex items-center gap-3.5 py-3 pl-7 pr-5 text-[15px] font-semibold transition-colors duration-300"
                          : "flex items-center gap-3.5 py-3 pl-7 pr-5 text-[15px] font-medium text-white transition-colors duration-300"
                    }
                    style={active ? { color: "var(--console-rail)" } : undefined}
                  >
                    <span aria-hidden="true" className="grid h-5 w-5 shrink-0 place-items-center">
                      {link.icon}
                    </span>
                    <span className={collapsed ? "sr-only" : undefined}>{link.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </nav>
    </div>
  );
}

/** Sidebar panel toggle: rail + chevron, flips when collapsed. */
function PanelToggleIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      aria-hidden="true"
      className={`transition-transform duration-300 ${collapsed ? "rotate-180" : ""}`}
    >
      <rect x="3.5" y="4.5" width="17" height="15" rx="2.5" />
      <path d="M9.5 4.5v15" />
      <path d="m14.5 9.5 2.5 2.5-2.5 2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Thin outline icons, matching the reference stroke weight. */
function IconCases() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5Z" strokeLinejoin="round" />
    </svg>
  );
}

function IconInsights() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M5 19V10M12 19V5M19 19v-7" strokeLinecap="round" />
    </svg>
  );
}

function IconAutopsy() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <rect x="4.5" y="5" width="15" height="15" rx="2" />
      <path d="M8 3.5v3M16 3.5v3M8 12h5.5" strokeLinecap="round" />
      <circle cx="15.5" cy="15.5" r="2.2" />
      <path d="m17 17 1.8 1.8" strokeLinecap="round" />
    </svg>
  );
}

function IconForesight() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 4v2.2M12 17.8V20M4.8 6.8l1.6 1.6M17.6 15.6l1.6 1.6M4 12h2.2M17.8 12H20M6.8 19.2l1.6-1.6M15.6 8.4l1.6-1.6" strokeLinecap="round" />
    </svg>
  );
}

function IconStudio() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path
        d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V20a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H4a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H10a1.7 1.7 0 0 0 1-1.5V4a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V10a1.7 1.7 0 0 0 1.5 1H20a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconAudit() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M8 4h7.5L19 7.5V19a1.5 1.5 0 0 1-1.5 1.5H8A1.5 1.5 0 0 1 6.5 19V5.5A1.5 1.5 0 0 1 8 4Z" strokeLinejoin="round" />
      <path d="M15 4v3.5H19M9.5 12h5M9.5 15.5h3.5" strokeLinecap="round" />
    </svg>
  );
}

function IconAdmin() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5.5 19.2c1.2-3.2 3.4-4.7 6.5-4.7s5.3 1.5 6.5 4.7" strokeLinecap="round" />
    </svg>
  );
}
