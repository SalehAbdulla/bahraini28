interface GlowingLinesProps {
  className?: string;
}

/**
 * Decorative animated "energy flow" background for the dark ink sections,
 * adapted from the reference design and recoloured to the Bahraini 28 mint
 * palette. Purely decorative — renders nothing interactive.
 */
export default function GlowingLines({ className = "" }: GlowingLinesProps) {
  return (
    <div
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}
      aria-hidden="true"
    >
      {/* Diagonal light-swoosh */}
      <div
        className="absolute -left-1/4 -top-1/4 h-[150%] w-[150%] opacity-[0.08]"
        style={{
          background:
            "linear-gradient(135deg, transparent 30%, rgba(109,177,147,0.7) 45%, rgba(163,210,190,0.45) 55%, transparent 70%)",
          animation: "swooshDrift 12s ease-in-out infinite alternate",
        }}
      />

      <svg
        className="absolute inset-0 h-full w-full"
        viewBox="0 0 1440 800"
        fill="none"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <linearGradient id="bh-glow-1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6db193" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#a3d2be" stopOpacity="0.1" />
          </linearGradient>
          <linearGradient id="bh-glow-2" x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#86c1a6" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#6db193" stopOpacity="0.08" />
          </linearGradient>
          <linearGradient id="bh-glow-3" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#a3d2be" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#6db193" stopOpacity="0.05" />
          </linearGradient>
          <filter id="bh-glow-filter">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <path
          d="M-100,400 C200,200 400,600 700,300 S1100,500 1540,250"
          stroke="url(#bh-glow-1)"
          strokeWidth="1.5"
          filter="url(#bh-glow-filter)"
          opacity="0.6"
        >
          <animate
            attributeName="d"
            values="M-100,400 C200,200 400,600 700,300 S1100,500 1540,250;M-100,350 C200,250 400,550 700,350 S1100,450 1540,300;M-100,400 C200,200 400,600 700,300 S1100,500 1540,250"
            dur="16s"
            repeatCount="indefinite"
          />
        </path>
        <path
          d="M-50,500 C300,300 500,700 800,400 S1200,600 1500,350"
          stroke="url(#bh-glow-2)"
          strokeWidth="1"
          filter="url(#bh-glow-filter)"
          opacity="0.45"
        >
          <animate
            attributeName="d"
            values="M-50,500 C300,300 500,700 800,400 S1200,600 1500,350;M-50,460 C300,350 500,650 800,450 S1200,550 1500,400;M-50,500 C300,300 500,700 800,400 S1200,600 1500,350"
            dur="20s"
            repeatCount="indefinite"
          />
        </path>
        <path
          d="M-80,300 C250,500 450,150 750,450 S1150,200 1520,450"
          stroke="url(#bh-glow-3)"
          strokeWidth="1"
          filter="url(#bh-glow-filter)"
          opacity="0.35"
        >
          <animate
            attributeName="d"
            values="M-80,300 C250,500 450,150 750,450 S1150,200 1520,450;M-80,340 C250,460 450,200 750,410 S1150,250 1520,410;M-80,300 C250,500 450,150 750,450 S1150,200 1520,450"
            dur="24s"
            repeatCount="indefinite"
          />
        </path>

        {[120, 340, 560, 780, 1000, 1220].map((cx, i) => (
          <circle
            key={i}
            cx={cx}
            cy={250 + Math.sin(i * 1.2) * 120}
            r="2"
            fill="#6db193"
            opacity="0.25"
          >
            <animate
              attributeName="opacity"
              values="0.15;0.4;0.15"
              dur={`${3 + i * 0.7}s`}
              repeatCount="indefinite"
            />
          </circle>
        ))}
      </svg>
    </div>
  );
}
