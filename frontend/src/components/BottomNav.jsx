import React from 'react';
import { MapPin, Activity, Bell, User } from 'lucide-react';
import { motion } from 'framer-motion';

export default function BottomNav() {
  const tabs = [
    { icon: MapPin, label: "Map" },
    { icon: Activity, label: "Status" },
    { icon: Bell, label: "Alerts" },
    { icon: User, label: "Profile" }
  ];

  return (
    <div className="absolute bottom-0 w-full p-4 z-50">
      <div className="glass rounded-3xl p-3 flex justify-around items-center">
        {tabs.map((tab, i) => (
          <motion.button 
            key={i}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            className={`flex flex-col items-center gap-1 p-2 rounded-xl transition-colors ${i === 0 ? 'text-primary-500' : 'text-slate-400 hover:text-slate-200'}`}
          >
            <tab.icon size={24} strokeWidth={2.5} />
            <span className="text-[10px] font-medium">{tab.label}</span>
            {i === 0 && (
              <motion.div layoutId="nav-indicator" className="w-1 h-1 bg-primary-500 rounded-full mt-1" />
            )}
          </motion.button>
        ))}
      </div>
    </div>
  );
}
