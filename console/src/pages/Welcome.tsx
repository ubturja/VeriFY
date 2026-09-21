import { useNavigate } from "react-router-dom";

export function WelcomePage() {
  const navigate = useNavigate();

  return (
    <div className="section-blur-enter flex flex-col items-center justify-center h-full text-center px-8 select-none">
      <div className="mb-8 relative">
        <div className="absolute inset-0 rounded-full blur-3xl opacity-30 animate-pulse"
          style={{ background: 'radial-gradient(circle, #8e3b31, #e5cf80)' }} />
        <div className="relative w-20 h-20 rounded-full flex items-center justify-center glow-crimson"
          style={{ background: 'linear-gradient(135deg, #8e3b31, #c9a050)' }}>
          <span className="text-3xl text-[#f0ebe9]">⬡</span>
        </div>
      </div>

      <p className="font-mono text-xs tracking-[0.3em] text-[#8a7470] uppercase mb-4">
        VeriFY AI · Automated File Scanner
      </p>
      <h1 className="text-5xl md:text-6xl mb-3 leading-tight font-display text-[#f0ebe9]">
        Scan, Analyze,<br />
        <em className="text-[#e5cf80] font-italic">and Verify.</em>
      </h1>
      <p className="text-[#8a7470] text-base max-w-md mb-10 leading-relaxed font-body">
        The AI engine automatically classifies inbound documents and analyzes discrepancies.
      </p>
      <button onClick={() => navigate('/overview')}
        className="px-8 py-3 rounded-full text-sm font-semibold tracking-wide transition-all duration-300 hover:scale-105 cursor-pointer glow-crimson"
        style={{ background: 'linear-gradient(135deg, #8e3b31, #b8963a)', color: '#f0ebe9' }}>
        Open Operations Desk →
      </button>
    </div>
  );
}
