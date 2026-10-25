"use client";

import React, { useState } from "react";

export function HeroCube({ size = 120 }: { size?: number }) {
  const [isHovered, setIsHovered] = useState(false);
  const half = size / 2;

  return (
    <div
      className="relative flex items-center justify-center select-none"
      style={{
        width: size * 1.5,
        height: size * 1.5,
        perspective: "800px",
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      title="WATTSON Evidence Core"
    >
      <div
        className="relative transition-transform duration-700 ease-out"
        style={{
          width: size,
          height: size,
          transformStyle: "preserve-3d",
          animation: isHovered
            ? "rotateCube 8s linear infinite"
            : "rotateCube 24s linear infinite",
        }}
      >
        {/* Front */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-center border border-[#292d30] bg-[#000000]/95 p-2 backdrop-blur-sm transition-colors duration-200"
          style={{
            transform: `translateZ(${half}px)`,
          }}
        >
          <div className="h-2 w-2 rounded-full bg-[#9281f7]/80" />
          <span className="mt-1 font-mono text-[9px] tracking-wider text-[#a1a4a5]">MEASURE</span>
        </div>

        {/* Back */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-center border border-[#292d30] bg-[#000000]/95 p-2 backdrop-blur-sm"
          style={{
            transform: `rotateY(180deg) translateZ(${half}px)`,
          }}
        >
          <div className="h-2 w-2 rounded-full bg-[#3ad389]/80" />
          <span className="mt-1 font-mono text-[9px] tracking-wider text-[#a1a4a5]">VERIFY</span>
        </div>

        {/* Right */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-center border border-[#292d30] bg-[#000000]/95 p-2 backdrop-blur-sm"
          style={{
            transform: `rotateY(90deg) translateZ(${half}px)`,
          }}
        >
          <div className="h-2 w-2 rounded-full bg-[#3b9eff]/80" />
          <span className="mt-1 font-mono text-[9px] tracking-wider text-[#a1a4a5]">SIMULATE</span>
        </div>

        {/* Left */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-center border border-[#292d30] bg-[#000000]/95 p-2 backdrop-blur-sm"
          style={{
            transform: `rotateY(-90deg) translateZ(${half}px)`,
          }}
        >
          <div className="h-2 w-2 rounded-full bg-[#baa7ff]/80" />
          <span className="mt-1 font-mono text-[9px] tracking-wider text-[#a1a4a5]">ANALYZE</span>
        </div>

        {/* Top */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-center border border-[#292d30] bg-[#000000]/95 p-2 backdrop-blur-sm"
          style={{
            transform: `rotateX(90deg) translateZ(${half}px)`,
          }}
        >
          <div className="h-2 w-2 rounded-full bg-[#ffffff]/80" />
          <span className="mt-1 font-mono text-[9px] tracking-wider text-[#a1a4a5]">APPROVE</span>
        </div>

        {/* Bottom */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-center border border-[#292d30] bg-[#000000]/95 p-2 backdrop-blur-sm"
          style={{
            transform: `rotateX(-90deg) translateZ(${half}px)`,
          }}
        >
          <div className="h-2 w-2 rounded-full bg-[#70b8ff]/80" />
          <span className="mt-1 font-mono text-[9px] tracking-wider text-[#a1a4a5]">EXECUTE</span>
        </div>
      </div>

      <style jsx>{`
        @keyframes rotateCube {
          0% {
            transform: rotateX(-22deg) rotateY(25deg);
          }
          50% {
            transform: rotateX(-22deg) rotateY(205deg);
          }
          100% {
            transform: rotateX(-22deg) rotateY(385deg);
          }
        }
      `}</style>
    </div>
  );
}
