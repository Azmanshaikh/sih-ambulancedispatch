import React from 'react';
import { motion } from 'framer-motion';

export default function MobileContainer({ children }) {
  return (
    <div className="min-h-screen w-full bg-slate-900 flex justify-center items-center overflow-hidden">
      {/* Phone constraint wrapper */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="w-full h-[100dvh] sm:h-[850px] sm:w-[400px] sm:rounded-[3rem] sm:border-[8px] sm:border-slate-800 bg-slate-950 relative overflow-hidden shadow-2xl flex flex-col"
      >
        {/* Top Status Bar Mock (only visible on desktop simulating phone) */}
        <div className="hidden sm:flex justify-between items-center px-6 py-3 absolute top-0 w-full z-50 pointer-events-none">
          <span className="text-xs font-semibold">9:41</span>
          <div className="flex gap-2 items-center">
            <div className="w-4 h-3 bg-white rounded-sm"></div>
            <div className="w-5 h-3 bg-white rounded-sm"></div>
          </div>
        </div>

        {/* Dynamic Island Mock */}
        <div className="hidden sm:block absolute top-2 left-1/2 -translate-x-1/2 w-28 h-7 bg-black rounded-full z-50"></div>

        {/* App Content */}
        <div className="flex-1 overflow-y-auto pb-20 sm:pt-12 pt-4 relative z-10">
          {children}
        </div>
      </motion.div>
    </div>
  );
}
