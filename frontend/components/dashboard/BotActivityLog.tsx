'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';

interface LogMessage {
  timestamp: string;
  message: string;
  level: 'info' | 'warning' | 'error';
}

export function BotActivityLog() {
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleLogMessage = (event: CustomEvent) => {
      const data = event.detail;
      if (data) {
        setLogs(prev => {
          const newLogs = [...prev, data].slice(-100); // Keep last 100 logs
          return newLogs;
        });
      }
    };

    window.addEventListener('bot-log-message' as any, handleLogMessage);

    return () => {
      window.removeEventListener('bot-log-message' as any, handleLogMessage);
    };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Bot Activity Log</CardTitle>
      </CardHeader>
      <CardContent>
        <div 
          ref={scrollRef}
          className="h-48 overflow-y-auto bg-black text-xs font-mono p-2 rounded-md space-y-1"
        >
          {logs.length === 0 && (
            <div className="text-gray-500 italic">Waiting for bot activity...</div>
          )}
          {logs.map((log, index) => (
            <div key={index} className={`
              ${log.level === 'error' ? 'text-red-400' : ''}
              ${log.level === 'warning' ? 'text-yellow-400' : ''}
              ${log.level === 'info' ? 'text-green-400' : ''}
            `}>
              <span className="text-gray-500">[{new Date(log.timestamp).toLocaleTimeString()}]</span> {log.message}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
