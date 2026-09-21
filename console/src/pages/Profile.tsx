export function ProfilePage() {
  return (
    <div className="section-blur-enter h-full overflow-y-auto space-y-6">
      <div>
        <p className="font-mono text-xs tracking-[0.25em] text-[#8a7470] uppercase mb-1">Account</p>
        <h2 className="text-3xl font-display text-[#f0ebe9]">Profile</h2>
      </div>

      <div className="flex items-center gap-6 card-glass rounded-xl p-6 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-[radial-gradient(ellipse_at_center,rgba(142,59,49,0.15)_0%,transparent_60%)] pointer-events-none blur-xl"></div>
        <div className="w-16 h-16 rounded-full flex items-center justify-center text-2xl font-semibold z-10 glow-crimson"
          style={{ background: 'linear-gradient(135deg, #8e3b31, #b8963a)', color: '#f0ebe9' }}>
          OP
        </div>
        <div className="z-10">
          <p className="text-lg font-semibold text-[#f0ebe9]">Operator Lead</p>
          <p className="text-sm font-mono text-[#8a7470]">admin@verify-ops.com</p>
          <div className="mt-1 inline-block px-2 py-0.5 rounded text-xs font-mono"
            style={{ background: 'rgba(229,207,128,0.12)', color: '#e5cf80', border: '1px solid rgba(229,207,128,0.3)' }}>
            System Administrator
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card-glass rounded-xl p-6 space-y-3">
          <p className="text-xs font-mono text-[#8a7470] uppercase tracking-wide">AI Engine Configuration</p>
          {[
            ['Classification model', 'VeriFY v2.1'],
            ['Auto Scan Trigger', 'Immediately on arrival'],
            ['Confidence threshold', '80%'],
            ['Spam confidence threshold', '90%'],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between items-center py-2 border-b border-[rgba(142,59,49,0.12)]">
              <span className="text-sm text-[#8a7470]">{k}</span>
              <span className="text-sm font-mono text-[#e5cf80]">{v}</span>
            </div>
          ))}
        </div>

        <div className="card-glass rounded-xl p-6 space-y-3">
          <p className="text-xs font-mono text-[#8a7470] uppercase tracking-wide">Notification Preferences</p>
          {[
            ['New doc check request', true],
            ['Discrepancy found alert', true],
            ['Daily ops summary', true],
            ['Spam quarantine digest', false],
          ].map(([label, active]) => (
            <div key={label as string} className="flex justify-between items-center py-2 border-b border-[rgba(142,59,49,0.12)]">
              <span className="text-sm text-[#8a7470]">{label as string}</span>
              <div className="w-10 h-5 rounded-full flex items-center"
                style={{ background: active ? 'linear-gradient(90deg, #8e3b31, #b8963a)' : 'rgba(37,28,26,1)', padding: '2px' }}>
                <div className="w-4 h-4 rounded-full bg-[#f0ebe9] transition-all"
                  style={{ marginLeft: active ? 'auto' : '0' }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
