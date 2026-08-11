export default function WelcomeModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[9999] bg-black/80 backdrop-blur-md flex items-center justify-center">
      <div className="border border-blue-500/30 rounded-3xl p-10 w-[360px] text-center" style={{ background: 'rgba(15,23,42,0.97)', boxShadow: '0 0 60px rgba(59,130,246,0.2)' }}>
        <div className="w-20 h-20 rounded-full bg-blue-600 border-4 border-blue-400 flex items-center justify-center mx-auto mb-5 text-4xl font-black text-white">🏥</div>
        <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-blue-400 mb-2">Hospital Portal</p>
        <h2 className="text-3xl font-black text-white uppercase tracking-tight mb-1">ACCESS</h2>
        <h3 className="text-2xl font-black text-blue-400 uppercase tracking-widest mb-6">GRANTED</h3>
        <p className="text-slate-400 text-sm mb-8">Welcome! You now have access to Notifications.</p>
        <button onClick={onClose} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-black py-4 rounded-2xl uppercase tracking-widest text-xs transition-all">Enter Portal</button>
      </div>
    </div>
  );
}
