import { useEffect, useRef, useState, type ReactNode } from "react";

interface RevealProps {
  children: ReactNode;
  className?: string;
  /** Extra delay (ms) before the reveal transition starts. */
  delay?: number;
  /** Vertical offset (px) the element animates up from. */
  y?: number;
}

/**
 * Lightweight scroll-reveal wrapper (no animation library): fades + slides
 * content up the first time it enters the viewport, then stays visible.
 * Mirrors the scroll-reveal language of the reference design.
 */
export default function Reveal({
  children,
  className = "",
  delay = 0,
  y = 24,
}: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setVisible(true);
            observer.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -48px 0px" }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "none" : `translateY(${y}px)`,
        transition: `opacity 0.6s cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms, transform 0.6s cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}
